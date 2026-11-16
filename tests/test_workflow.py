import json

from difftrial.config import ROOT
from difftrial.exports import compare, export_bundle
from difftrial.providers import Generation, ProviderError
from difftrial.schemas import Plan, Proposal, Review, ValidationRequest
from difftrial.workflow import Worker
from difftrial.workflow import test_outcome as outcome

FIXTURES = json.loads((ROOT / "tests/fixtures/repairs.json").read_text(encoding="utf-8"))


class DeterministicAdapter:
    def __init__(self, config, benchmark="py-intervals", successful=True):
        self.benchmark, self.successful = benchmark, successful

    async def generate(self, instructions, context, schema, cancelled):
        if schema is Plan:
            value = Plan(summary="Deterministic test fixture plan", steps=["Apply known fixture patch"])
        elif schema is Proposal:
            edit = FIXTURES[self.benchmark].copy()
            if not self.successful:
                original = ROOT / "benchmarks" / self.benchmark / edit["path"]
                edit["content"] = original.read_text() + (
                    "\n# unsuccessful control\n"
                    if self.benchmark.startswith("py")
                    else "\n// unsuccessful control\n"
                )
            value = Proposal(summary="Deterministic test fixture proposal", edits=[edit])
        elif schema is ValidationRequest:
            value = ValidationRequest(summary="Request controlled checks", checks=["tests", "static"])
        else:
            value = Review(
                summary="Deterministic fixture review, not a model judgment",
                verdict="accept" if self.successful else "reject",
                findings=[],
            )
        return Generation(value=value, usage={})


class FakeRunner:
    def __init__(self, *args):
        self.count = 0

    def setup(self, *args):
        return "fake"

    def check(self, image, source, profile, check):
        self.count += 1
        failed = check == "tests" and self.count == 1
        return {
            "exit_code": int(failed),
            "report_valid": True,
            "passed": 1 if failed else 2,
            "failed": int(failed),
            "skipped": 0,
            "duration": 0,
            "log": "unit-test double",
            "cases": [
                {"name": "existing", "status": "passed"},
                {"name": "regression", "status": "failed" if failed else "passed"},
            ],
        }

    def close(self):
        pass


def test_workflow_persists_roles_attempts_and_separate_verdicts(store, queued):
    ident = queued()
    Worker(store, FakeRunner, DeterministicAdapter).once()
    detail = store.detail(ident)
    assert detail["status"] == "completed"
    assert detail["outcome"] == "fixed"
    assert detail["verdict"] == "accept"
    assert len(detail["attempts"]) == 1
    assert [e["payload"]["role"] for e in detail["events"] if e["kind"] == "role"] == [
        "planner",
        "implementer",
        "validator",
        "reviewer",
    ]
    from difftrial.config import data_dir

    assert (data_dir() / "runs" / ident / "bundle.json").is_file()


def test_provider_failure_is_infrastructure_not_bad_repair(store, queued):
    ident = queued()

    class BrokenAdapter:
        def __init__(self, config):
            pass

        async def generate(self, *args):
            raise ProviderError("rate_limit", "Provider rate limited")

    Worker(store, FakeRunner, BrokenAdapter).once()
    detail = store.detail(ident)
    assert detail["status"] == "infrastructure_error"
    assert detail["outcome"] == "not_run"
    summary = compare([export_bundle(detail)["run"]])[0]
    assert summary["eligible"] == 0 and summary["infrastructure_errors"] == 1


def test_model_cannot_override_actual_failure():
    baseline = {"tests": {"exit_code": 1, "failed": 1, "cases": [{"name": "existing", "status": "passed"}]}}
    patched = {
        "tests": {"exit_code": 1, "report_valid": True, "cases": [{"name": "existing", "status": "passed"}]},
        "static": {"exit_code": 0},
    }
    assert outcome(baseline, patched)[0] == "failing"
    patched["tests"]["cases"] = []
    assert outcome(baseline, patched)[0] == "regressed"


def test_source_tampering_detected(store, queued, tmp_path):
    ident = queued()
    detail = store.detail(ident)
    (tmp_path / "tasks" / detail["task_id"] / "tests/test_regression.py").write_text("pass")
    Worker(store, FakeRunner, DeterministicAdapter).once()
    assert "changed since import" in store.detail(ident)["error"]


def test_active_cancellation_is_finalized_by_worker(store, queued):
    ident = queued()

    class CancelDuringSetup(FakeRunner):
        def setup(self, *args):
            store.cancel(ident)
            return "fake"

    Worker(store, CancelDuringSetup, DeterministicAdapter).once()
    detail = store.detail(ident)
    assert detail["status"] == "cancelled"
    assert detail["outcome"] == "not_run"
    assert not detail["attempts"]


def test_comparisons_separate_different_limits(store, queued):
    ids = [queued(), queued()]
    worker = Worker(store, FakeRunner, DeterministicAdapter)
    worker.once()
    worker.once()
    runs = [export_bundle(store.detail(i))["run"] for i in ids]
    assert len(compare(runs)) == 1
    runs[1]["limits"]["command_seconds"] += 1
    assert len(compare(runs)) == 2
