"""Record staged model experiments when the model and Docker run on different hosts.

Only original benchmarks are supported. No credentials enter CI. Baselines are
measured before local generation; candidate tests are measured before review.
"""

import argparse
import asyncio
import json
import os
import shutil
import time
from pathlib import Path

from difftrial.benchmarks import catalog, prepare_benchmark
from difftrial.config import ROOT, Limits, data_dir, local_codex_defaults
from difftrial.db import Attempt, Event, Run, Store, Task, uid
from difftrial.exports import compare, export_bundle
from difftrial.providers import adapter
from difftrial.runner import DockerRunner
from difftrial.schemas import Plan, Proposal, ProviderConfig, Review, ValidationRequest
from difftrial.security import apply_proposal, source_files, tree_hash
from difftrial.workflow import RUBRIC, SYSTEM, test_outcome

TASKS = ["py-intervals", "ts-versions"]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def baseline(output):
    results = []
    for ident in TASKS:
        source = ROOT / "benchmarks" / ident
        item = next(b for b in catalog() if b["id"] == ident)
        runner = DockerRunner(uid(), Limits())
        try:
            image = runner.setup(source, item["profile"])
            reports = {
                check: runner.check(image, source, item["profile"], check) for check in ("tests", "static")
            }
            assert reports["tests"]["failed"] > 0, json.dumps(reports)
            results.append(
                {
                    "benchmark_id": ident,
                    "source_sha256": tree_hash(source),
                    "reports": reports,
                    "measured_at": time.time(),
                    "ci_run": os.getenv("GITHUB_RUN_ID"),
                }
            )
        finally:
            runner.close()
    save(output, results)


async def generate(baselines, output):
    endpoint, model = local_codex_defaults()
    config = ProviderConfig(endpoint=endpoint, model=model)
    provider = adapter(config)
    candidates = []
    for measured in load(baselines):
        ident = measured["benchmark_id"]
        item = next(b for b in catalog() if b["id"] == ident)
        source = ROOT / "benchmarks" / ident
        assert tree_hash(source) == measured["source_sha256"], "Baseline source differs from candidate source"
        context = {
            "issue": item["issue"],
            "files": source_files(source, item["profile"]),
            "baseline": measured["reports"],
        }
        roles = []
        for name, schema in [("planner", Plan), ("implementer", Proposal), ("validator", ValidationRequest)]:
            if name == "validator":
                context["allowed_tools"] = ["tests", "static"]
            result = await provider.generate(
                SYSTEM + f"\nRole: {name}. Prompt repair-v1.", json.dumps(context), schema
            )
            roles.append(
                {
                    "role": name,
                    "output": result.value.model_dump(),
                    "usage": result.usage,
                    "created": time.time(),
                }
            )
            context[name] = result.value.model_dump()
        candidates.append(
            {
                "benchmark_id": ident,
                "source_sha256": measured["source_sha256"],
                "baseline_ci_run": measured["ci_run"],
                "provider": {"kind": config.kind, "model": config.model, "transport": config.transport},
                "roles": roles,
                "proposal": roles[1]["output"],
            }
        )
    control = candidates[0].copy()
    control["provider"] = {"kind": "control", "model": "deliberately-incomplete-patch", "transport": "none"}
    control["roles"] = []
    original = (ROOT / "benchmarks/py-intervals/src/repair.py").read_text()
    control["proposal"] = {
        "summary": "Negative control: a comment-only patch intentionally leaves the bug in place",
        "edits": [
            {
                "path": "src/repair.py",
                "content": original + "\n# Negative control: the boundary comparison is unchanged.\n",
            }
        ],
    }
    candidates.append(control)
    save(output, candidates)


def evaluate(candidates, output):
    store = Store()
    bundles = []
    for candidate in load(candidates):
        task_id, run_id = uid(), uid()
        original = data_dir() / "tasks" / task_id
        item, source = prepare_benchmark(candidate["benchmark_id"], original)
        assert source["tree_sha256"] == candidate["source_sha256"]
        workspace = data_dir() / "runs" / run_id / "workspace"
        shutil.copytree(original, workspace)
        with store.session() as s:
            s.add(
                Task(
                    id=task_id,
                    title=item["title"],
                    issue=item["issue"],
                    profile=item["profile"],
                    source=source,
                )
            )
            s.flush()
            s.add(
                Run(
                    id=run_id,
                    task_id=task_id,
                    provider=candidate["provider"],
                    limits=Limits().model_dump(),
                    status="running",
                    stage="baseline",
                    started=time.time(),
                )
            )
        runner = DockerRunner(
            run_id, Limits(), emit=lambda kind, **payload: store.emit(run_id, kind, **payload)
        )
        try:
            image = runner.setup(original, item["profile"])
            baseline_reports = {
                c: runner.check(image, original, item["profile"], c) for c in ("tests", "static")
            }
            store.update(run_id, baseline=baseline_reports)
            usage = {}
            for role in candidate["roles"]:
                for key, value in role["usage"].items():
                    usage[key] = usage.get(key, 0) + value
                with store.session() as s:
                    s.add(
                        Event(
                            run_id=run_id,
                            kind="role",
                            created=role["created"],
                            payload={
                                "role": role["role"],
                                "summary": role["output"]["summary"],
                                "usage": role["usage"],
                            },
                        )
                    )
            store.emit(
                run_id,
                "provenance",
                message=f"Staged experiment: model proposals followed baseline CI run {candidate['baseline_ci_run']}; execution CI run {os.getenv('GITHUB_RUN_ID')}. No provider credentials were sent to CI.",
            )
            patch = apply_proposal(workspace, Proposal.model_validate(candidate["proposal"]), item["profile"])
            reports = {c: runner.check(image, workspace, item["profile"], c) for c in ("tests", "static")}
            outcome, regressions = test_outcome(baseline_reports, reports)
            reports["regressions"] = regressions
            with store.session() as s:
                s.add(Attempt(run_id=run_id, number=1, patch=patch, reports=reports, review={}))
            store.update(
                run_id,
                status="completed",
                stage="completed",
                outcome=outcome,
                usage=usage,
                finished=time.time(),
            )
            store.emit(
                run_id,
                "completed",
                outcome=outcome,
                message="Docker execution completed; independent model review is pending",
            )
            bundle = export_bundle(store.detail(run_id))
            bundle["run"]["protocol"] = "staged_ci"
            bundle["run"]["prompt_version"] = "repair-v1-staged"
            bundles.append(bundle)
        finally:
            runner.close()
    save(output, bundles)


async def review(evaluations, output):
    endpoint, model = local_codex_defaults()
    provider = adapter(ProviderConfig(endpoint=endpoint, model=model))
    bundles = load(evaluations)
    for bundle in bundles:
        run = bundle["run"]
        run["protocol"] = "staged_ci"
        run["prompt_version"] = "repair-v1-staged"
        if run["provider"]["kind"] == "control":
            review = Review(
                summary="Deliberately incomplete negative control. Runner confirms that the regression still fails. No model review was requested.",
                verdict="reject",
                findings=[
                    {
                        "rule": "R01",
                        "severity": "error",
                        "message": "Comment-only patch leaves the issue unresolved.",
                    }
                ],
            )
            usage = {}
        else:
            result = await provider.generate(
                SYSTEM + "\nRole: reviewer. Rubric review-v1.",
                json.dumps(
                    {
                        "issue": run["task"]["issue"],
                        "patch": run["attempts"][0]["patch"],
                        "baseline": run["baseline"],
                        "reports": run["attempts"][0]["reports"],
                        "rubric": RUBRIC,
                    }
                ),
                Review,
            )
            review, usage = result.value, result.usage
        run["verdict"] = review.verdict
        run["attempts"][0]["review"] = review.model_dump()
        for key, value in usage.items():
            run["usage"][key] = run["usage"].get(key, 0) + value
        run["events"].append(
            {
                "id": max(e["id"] for e in run["events"]) + 1,
                "kind": "role",
                "created": time.time(),
                "payload": {
                    "role": "reviewer" if run["provider"]["kind"] != "control" else "negative control",
                    "summary": review.summary,
                    "usage": usage,
                },
            }
        )
        run["events"].sort(key=lambda e: e["created"])
        # Export again through the same allowlist and redaction boundary.
        sanitized = export_bundle(run)
        save(Path(output) / f"{run['id']}.json", sanitized)
    save(
        Path(output) / "index.json",
        {
            "schema_version": "difftrial.demo.v1",
            "recorded": True,
            "runs": [export_bundle(b["run"])["run"] for b in bundles],
            "benchmarks": catalog(),
            "comparisons": compare([b["run"] for b in bundles]),
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["baseline", "generate", "evaluate", "review"])
    parser.add_argument("--input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.phase == "baseline":
        baseline(args.output)
    elif args.phase == "generate":
        asyncio.run(generate(args.input, args.output))
    elif args.phase == "evaluate":
        evaluate(args.input, args.output)
    else:
        asyncio.run(review(args.input, args.output))
