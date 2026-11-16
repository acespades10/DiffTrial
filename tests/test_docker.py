import json
import shutil

import pytest
from difftrial.benchmarks import catalog
from difftrial.config import ROOT, Limits
from difftrial.runner import DockerRunner, ExecutionError, docker_status
from difftrial.schemas import Proposal
from difftrial.security import apply_proposal
from difftrial.workflow import Worker
from test_workflow import DeterministicAdapter

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not docker_status()["available"], reason="Docker Linux engine unavailable"),
]


@pytest.mark.parametrize("benchmark", [item["id"] for item in catalog()])
def test_all_original_benchmarks_fail_then_pass(benchmark, tmp_path):
    item = next(b for b in catalog() if b["id"] == benchmark)
    source = tmp_path / "source"
    shutil.copytree(ROOT / "benchmarks" / benchmark, source)
    runner = DockerRunner("test-" + benchmark, Limits())
    try:
        image = runner.setup(source, item["profile"])
        baseline = runner.check(image, source, item["profile"], "tests")
        assert baseline["exit_code"] != 0 and baseline["failed"] > 0 and baseline["passed"] > 0
        fixture = json.loads((ROOT / "tests/fixtures/repairs.json").read_text(encoding="utf-8"))[benchmark]
        apply_proposal(source, Proposal(summary="Known repair fixture", edits=[fixture]), item["profile"])
        result = runner.check(image, source, item["profile"], "tests")
        assert result["exit_code"] == 0 and result["failed"] == 0 and result["report_valid"]
        assert runner.check(image, source, item["profile"], "static")["exit_code"] == 0
    finally:
        runner.close()


@pytest.mark.parametrize(
    "benchmark,success", [("py-intervals", True), ("ts-versions", True), ("py-intervals", False)]
)
def test_full_worker_docker_success_and_unsuccessful(store, queued, benchmark, success):
    ident = queued(benchmark)
    Worker(store, DockerRunner, lambda config: DeterministicAdapter(config, benchmark, success)).once()
    result = store.detail(ident)
    assert result["status"] == "completed", result["error"]
    assert result["outcome"] == ("fixed" if success else "failing")
    assert len(result["attempts"]) == (1 if success else 2)


def test_isolation_credentials_and_timeout(monkeypatch):
    monkeypatch.setenv("CODEX_LB_API_KEY", "must-not-enter-container")
    runner = DockerRunner("isolation", Limits(command_seconds=5))
    try:
        name = runner.create(
            "difftrial-python:v1",
            [
                "python",
                "-c",
                "import os,pathlib,socket; assert os.getuid()==10001; assert 'CODEX_LB_API_KEY' not in os.environ; assert not pathlib.Path('/var/run/docker.sock').exists(); assert pathlib.Path('/proc/self/status').read_text().split('CapEff:')[1].split()[0]=='0000000000000000'; s=socket.socket(); s.settimeout(1); assert s.connect_ex(('1.1.1.1',443)) != 0; print('isolation verified')",
            ],
        )
        code, log, _ = runner.execute(name)
        assert code == 0 and "isolation verified" in log
        inspect = json.loads(runner.call(["inspect", name]).stdout)[0]
        assert not inspect["HostConfig"]["Binds"]
        assert inspect["HostConfig"]["ReadonlyRootfs"]
        assert inspect["HostConfig"]["NetworkMode"] == "none"
        assert inspect["HostConfig"]["Memory"] == 512 * 1024 * 1024
        slow = runner.create("difftrial-python:v1", ["python", "-c", "import time;time.sleep(30)"])
        with pytest.raises(ExecutionError, match="timeout"):
            runner.execute(slow)
    finally:
        runner.close()
