"""Trusted command selection. Repository scripts never choose the executed command."""

import json
import os
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

profile, check = sys.argv[1:]
if profile == "python":
    command = (
        [
            "python",
            "-m",
            "pytest",
            "tests",
            "-q",
            "-c",
            "/dev/null",
            "-p",
            "no:cacheprovider",
            "--junitxml=/tmp/tests.xml",
        ]
        if check == "tests"
        else ["ruff", "check", "--isolated", "--select", "E9,F63,F7,F82", "src"]
    )
else:
    command = (
        [
            "node",
            "node_modules/vitest/vitest.mjs",
            "run",
            "--config",
            "/opt/runner/vitest.config.mjs",
            "--configLoader",
            "native",
            "--reporter=json",
            "--outputFile=/tmp/tests.json",
        ]
        if check == "tests"
        else [
            "node",
            "node_modules/typescript/bin/tsc",
            "--noEmit",
            "--strict",
            "--target",
            "es2022",
            "--module",
            "nodenext",
            "--moduleResolution",
            "nodenext",
            "--skipLibCheck",
            *[str(p) for p in Path("src").rglob("*.ts")],
        ]
    )
process = subprocess.Popen(command, start_new_session=True)
try:
    exit_code = process.wait(timeout=int(os.environ.get("DIFFTRIAL_COMMAND_SECONDS", "300")))
except subprocess.TimeoutExpired:
    os.killpg(process.pid, signal.SIGKILL)
    process.wait()
    print("DiffTrial command deadline exceeded", file=sys.stderr)
    sys.exit(124)
report = {"exit_code": exit_code, "check": check, "cases": [], "report_valid": check == "static"}
try:
    if check == "tests" and profile == "python":
        document = Path("/tmp/tests.xml")
        if document.stat().st_size > 2_000_000:
            raise ValueError("Oversized report")
        root = ET.fromstring(document.read_bytes())
        for case in root.iter("testcase"):
            state = (
                "failed"
                if case.find("failure") is not None or case.find("error") is not None
                else "skipped"
                if case.find("skipped") is not None
                else "passed"
            )
            report["cases"].append(
                {"name": case.get("classname", "") + "::" + case.get("name", ""), "status": state}
            )
        report["report_valid"] = bool(report["cases"])
    elif check == "tests":
        document = Path("/tmp/tests.json")
        if document.stat().st_size > 2_000_000:
            raise ValueError("Oversized report")
        data = json.loads(document.read_text())
        for suite in data.get("testResults", []):
            for case in suite.get("assertionResults", []):
                report["cases"].append({"name": case["fullName"], "status": case["status"]})
        report["report_valid"] = bool(report["cases"])
except (OSError, ValueError, ET.ParseError, KeyError):
    report["report_valid"] = False
for status in ("passed", "failed", "skipped"):
    report[status] = sum(c["status"] == status for c in report["cases"])
Path("/tmp/result.json").write_text(json.dumps(report))
sys.exit(exit_code)
