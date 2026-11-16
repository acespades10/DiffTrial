import hashlib
import json
import os
import re
from collections import defaultdict


def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    for name, secret in os.environ.items():
        if re.search(r"KEY|TOKEN|PASSWORD|SECRET", name, re.I) and len(secret) >= 6:
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"(?i)(?:Bearer\s+)[^\s\"']+", "Bearer [REDACTED]", value)
    value = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{12,})", "[REDACTED]", value)
    value = re.sub(
        r"(?i)(api[_-]?key|password|token|secret)(\s*[=:]\s*)[^\s,;\"']+", r"\1\2[REDACTED]", value
    )
    value = re.sub(r"[A-Za-z]:[\\/][^\n\"<>]*", "[LOCAL_PATH]", value)
    value = re.sub(r"/(?:Users|home|root|private|var/folders)/[^\s\"']+", "[LOCAL_PATH]", value)
    return value


def subset(data, keys):
    return {k: data[k] for k in keys if k in data}


def clean_report(report):
    result = subset(
        report,
        (
            "exit_code",
            "check",
            "report_valid",
            "passed",
            "failed",
            "skipped",
            "duration",
            "network",
            "executor",
            "log",
        ),
    )
    result["cases"] = [subset(c, ("name", "status")) for c in report.get("cases", [])]
    return result


def clean_reports(reports):
    return {k: clean_report(reports[k]) for k in ("tests", "static") if k in reports} | (
        {"regressions": reports["regressions"]} if "regressions" in reports else {}
    )


def export_bundle(detail):
    run = subset(
        detail,
        (
            "id",
            "status",
            "stage",
            "outcome",
            "verdict",
            "created",
            "started",
            "finished",
            "error",
            "prompt_version",
            "rubric_version",
            "limits",
            "usage",
        ),
    )
    run["provider"] = subset(detail["provider"], ("kind", "transport", "model"))
    run["protocol"] = detail.get("protocol", "local_worker")
    provider = detail["provider"]
    if (
        provider.get("input_price_per_million") is not None
        and provider.get("output_price_per_million") is not None
        and {"input_tokens", "output_tokens"} <= detail["usage"].keys()
    ):
        run["cost_usd"] = (
            provider["input_price_per_million"] * detail["usage"]["input_tokens"]
            + provider["output_price_per_million"] * detail["usage"]["output_tokens"]
        ) / 1_000_000
    run["task"] = subset(detail["task"], ("id", "title", "issue", "profile"))
    run["task"]["source"] = subset(
        detail["task"]["source"],
        ("kind", "repository", "commit", "version", "benchmark_id", "tree_sha256", "evaluation"),
    )
    run["baseline"] = clean_reports(detail["baseline"])
    run["attempts"] = []
    for attempt in detail["attempts"]:
        review = subset(attempt["review"], ("summary", "verdict"))
        review["findings"] = [
            subset(f, ("rule", "severity", "message", "path")) for f in attempt["review"].get("findings", [])
        ]
        run["attempts"].append(
            {
                "number": attempt["number"],
                "patch": attempt["patch"],
                "reports": clean_reports(attempt["reports"]),
                "review": review,
            }
        )
    run["events"] = [
        {
            "id": e["id"],
            "kind": e["kind"],
            "created": e["created"],
            "payload": subset(
                e["payload"],
                (
                    "name",
                    "role",
                    "summary",
                    "tool",
                    "message",
                    "exit_code",
                    "duration",
                    "usage",
                    "requested",
                    "executed",
                    "outcome",
                    "verdict",
                    "code",
                    "log",
                ),
            ),
        }
        for e in detail["events"]
    ]
    for original, exported in zip(detail["events"], run["events"]):
        if original["kind"] == "patch_rejected" and isinstance(original["payload"].get("proposal"), dict):
            proposal = original["payload"]["proposal"]
            exported["payload"]["proposal"] = {
                "summary": proposal.get("summary", ""),
                "edits": [subset(edit, ("path", "content")) for edit in proposal.get("edits", [])],
            }
    run = redact(run)
    artifacts = {"baseline.json": json.dumps(run["baseline"], indent=2)}
    for check in ("tests", "static"):
        if check in run["baseline"]:
            artifacts[f"baseline-{check}.log"] = run["baseline"][check].get("log", "")
    for attempt in run["attempts"]:
        artifacts[f"attempt-{attempt['number']}.diff"] = attempt["patch"]
        artifacts[f"attempt-{attempt['number']}-reports.json"] = json.dumps(attempt["reports"], indent=2)
        for check in ("tests", "static"):
            if check in attempt["reports"]:
                artifacts[f"attempt-{attempt['number']}-{check}.log"] = attempt["reports"][check].get(
                    "log", ""
                )
    for event in run["events"]:
        if event["kind"] == "patch_rejected" and "proposal" in event["payload"]:
            artifacts[f"rejected-proposal-{event['id']}.json"] = json.dumps(
                event["payload"]["proposal"], indent=2
            )
    return {
        "schema_version": "difftrial.bundle.v1",
        "recorded": True,
        "run": run,
        "artifacts": [
            {"name": name, "sha256": hashlib.sha256(content.encode()).hexdigest(), "content": content}
            for name, content in artifacts.items()
        ],
    }


def compare(runs):
    cohorts = defaultdict(list)
    for run in runs:
        key = json.dumps(
            {
                "source": run["task"]["source"],
                "limits": run["limits"],
                "prompt": run["prompt_version"],
                "rubric": run["rubric_version"],
                "protocol": run.get("protocol", "local_worker"),
            },
            sort_keys=True,
        )
        cohorts[key].append(run)
    result = []
    for key, group in cohorts.items():
        for provider in sorted({(r["provider"]["kind"], r["provider"]["model"]) for r in group}):
            selected = [r for r in group if (r["provider"]["kind"], r["provider"]["model"]) == provider]
            eligible = [
                r
                for r in selected
                if r["status"] in {"completed", "failed"}
                and r["task"]["source"]["kind"] == "benchmark"
                and r["baseline"].get("tests", {}).get("failed", 0) > 0
            ]
            fixed = sum(r["outcome"] == "fixed" for r in eligible)
            result.append(
                {
                    "cohort": hashlib.sha256(key.encode()).hexdigest()[:12],
                    "task": group[0]["task"]["title"],
                    "version": group[0]["task"]["source"]["version"],
                    "provider": provider[0],
                    "model": provider[1],
                    "total": len(selected),
                    "eligible": len(eligible),
                    "fixed": fixed,
                    "fix_rate": fixed / len(eligible) if eligible else None,
                    "regressions": sum(r["outcome"] == "regressed" for r in selected),
                    "infrastructure_errors": sum(
                        r["status"] in {"infrastructure_error", "interrupted"} for r in selected
                    ),
                    "failed_repairs": sum(
                        r["status"] == "failed"
                        or (r["status"] == "completed" and r["outcome"] not in {"fixed", "passing"})
                        for r in selected
                    ),
                    "duration_seconds": sum(
                        max(0, (r["finished"] or r["created"]) - (r["started"] or r["created"]))
                        for r in selected
                    ),
                    "input_tokens": sum(r["usage"].get("input_tokens", 0) for r in selected),
                    "output_tokens": sum(r["usage"].get("output_tokens", 0) for r in selected),
                    "usage_available_runs": sum(bool(r["usage"]) for r in selected),
                }
            )
    return result
