import io
import json
import shutil
import subprocess
import tarfile
import time
import uuid
from pathlib import Path

from .config import ROOT, Limits
from .providers import Cancelled
from .security import SetupError


class ExecutionError(RuntimeError):
    pass


def docker_status():
    binary = shutil.which("docker")
    if not binary:
        return {
            "available": False,
            "message": "Docker is not installed or not on PATH. Install Docker Desktop and enable Linux containers.",
        }
    try:
        result = subprocess.run(
            [binary, "info", "--format", "{{.OSType}}"], capture_output=True, timeout=10, text=True
        )
        if result.returncode == 0 and result.stdout.strip() == "linux":
            return {"available": True, "message": "Docker Linux engine is available"}
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"available": False, "message": "Start Docker's Linux engine and try again."}


class DockerRunner:
    def __init__(self, run_id: str, limits: Limits, cancelled=lambda: False, emit=lambda *a, **k: None):
        if not docker_status()["available"]:
            raise ExecutionError(docker_status()["message"])
        self.run_id, self.limits, self.cancelled, self.emit = run_id, limits, cancelled, emit
        self.containers, self.images = set(), set()

    def call(self, args, *, timeout=30, check=True, input=None):
        try:
            result = subprocess.run(["docker", *args], input=input, capture_output=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ExecutionError("Docker command failed or exceeded its deadline") from exc
        if check and result.returncode:
            raise ExecutionError("Docker operation failed: " + result.stderr.decode(errors="replace")[-1000:])
        return result

    def flags(self, name, offline=True):
        flags = [
            "--name",
            name,
            "--label",
            "difftrial.run=" + self.run_id,
            "--user",
            "10001:10001",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory",
            f"{self.limits.memory_mb}m",
            "--memory-swap",
            f"{self.limits.memory_mb}m",
            "--cpus",
            str(self.limits.cpus),
            "--pids-limit",
            "128",
            "--ulimit",
            "nofile=256:256",
            "--log-driver",
            "local",
            "--log-opt",
            "max-size=1m",
            "--log-opt",
            "max-file=2",
        ]
        if offline:
            flags += [
                "--network=none",
                "--read-only",
                "--env",
                f"DIFFTRIAL_COMMAND_SECONDS={self.limits.command_seconds}",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=128m,uid=10001,gid=10001",
            ]
        return flags

    def create(self, image, command, offline=True):
        name = "difftrial-" + uuid.uuid4().hex
        self.call(["create", *self.flags(name, offline), image, *command])
        self.containers.add(name)
        return name

    def copy_source(self, name, source: Path):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for path in sorted(source.rglob("*")):
                if path.is_symlink():
                    raise SetupError("Symlinks cannot enter execution containers")
                if not path.is_file():
                    continue
                info = tarfile.TarInfo(path.relative_to(source).as_posix())
                content = path.read_bytes()
                info.size, info.mode, info.uid, info.gid = len(content), 0o444, 10001, 10001
                archive.addfile(info, io.BytesIO(content))
        self.call(["cp", "-", f"{name}:/work"], input=buffer.getvalue())

    def execute(self, name):
        self.call(["start", name])
        started, reason = time.monotonic(), None
        while True:
            if self.cancelled():
                reason = "cancelled"
            elif time.monotonic() - started >= self.limits.command_seconds:
                reason = "timeout"
            if reason:
                self.call(["kill", name], check=False)
                break
            state = json.loads(self.call(["inspect", "--format", "{{json .State}}", name]).stdout)
            if not state["Running"]:
                break
            time.sleep(0.2)
        state = json.loads(self.call(["inspect", "--format", "{{json .State}}", name]).stdout)
        logs = self.call(["logs", "--tail", "1000", name], check=False)
        log = (logs.stdout + logs.stderr).decode(errors="replace")[-64000:]
        if reason == "cancelled":
            raise Cancelled("Run cancelled or deadline reached")
        if reason == "timeout" or state.get("ExitCode") == 124 or state.get("OOMKilled"):
            raise ExecutionError(
                "Container exceeded its memory limit" if state.get("OOMKilled") else "Command timeout"
            )
        return state["ExitCode"], log, round(time.monotonic() - started, 3)

    def setup(self, source, profile):
        base = "difftrial-" + profile + ":v1"
        if self.call(["image", "inspect", base], check=False).returncode:
            raise ExecutionError(f"Runner image missing. Run: difftrial build-runners ({base})")
        command = (
            [
                "python",
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--require-hashes",
                "--only-binary=:all:",
                "--target",
                "/work/deps",
                "-r",
                "requirements.lock",
            ]
            if profile == "python"
            else ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--cache", "/tmp/npm-cache"]
        )
        name = self.create(base, command, offline=False)
        self.copy_source(name, source)
        code, log, duration = self.execute(name)
        self.emit("tool", tool="setup", exit_code=code, duration=duration, log=log)
        if code:
            raise ExecutionError("Dependency installation failed; inspect the setup log and lockfile")
        image = "difftrial-prepared:" + uuid.uuid4().hex
        self.call(["commit", name, image], timeout=60)
        self.images.add(image)
        return image

    def check(self, image, source, profile, check):
        command = ["python" if profile == "python" else "python3", "/opt/runner/execute.py", profile, check]
        staging = self.create(image, command, offline=False)
        self.copy_source(staging, source)
        snapshot = "difftrial-prepared:" + uuid.uuid4().hex
        self.call(["commit", staging, snapshot], timeout=60)
        self.images.add(snapshot)
        name = self.create(snapshot, command)
        exit_code, log, duration = self.execute(name)
        report = {"report_valid": False, "cases": [], "passed": 0, "failed": 0, "skipped": 0}
        # tmpfs disappears when a container exits. The trusted wrapper emits its
        # bounded report before exit, while Docker retains stdout independently.
        marker = "DIFFTRIAL_REPORT_V1:"
        if marker in log:
            try:
                prefix, encoded = log.rsplit(marker, 1)
                line, _, suffix = encoded.partition("\n")
                data = json.loads(line)
                cases = data.get("cases")
                if (
                    isinstance(cases, list)
                    and len(cases) <= 10000
                    and all(
                        isinstance(c, dict)
                        and isinstance(c.get("name"), str)
                        and c.get("status") in {"passed", "failed", "skipped", "pending", "todo"}
                        for c in cases
                    )
                ):
                    report = {"cases": cases, "report_valid": data.get("report_valid") is True}
                    for status in ("passed", "failed", "skipped"):
                        report[status] = sum(c["status"] == status for c in cases)
                    log = prefix + suffix
            except (ValueError, KeyError, TypeError, AttributeError):
                pass
        # The daemon's process exit status always wins over a repository-written report.
        report.update(
            exit_code=exit_code, log=log, duration=duration, check=check, network="none", executor="docker"
        )
        self.emit("tool", tool=check, exit_code=exit_code, duration=duration)
        return report

    def close(self):
        for name in self.containers:
            self.call(["rm", "-f", name], check=False)
        for image in self.images:
            self.call(["image", "rm", "-f", image], check=False)


def build_runners():
    if not docker_status()["available"]:
        raise ExecutionError(docker_status()["message"])
    for profile in ("python", "typescript"):
        subprocess.run(
            [
                "docker",
                "build",
                "-f",
                str(ROOT / "runners" / f"{profile}.Dockerfile"),
                "-t",
                f"difftrial-{profile}:v1",
                str(ROOT / "runners"),
            ],
            check=True,
        )
