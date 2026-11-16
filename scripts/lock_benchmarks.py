"""Refresh the identical npm dependency graph for the six TypeScript tasks."""

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
base = ROOT / "benchmarks/ts-versions"
subprocess.run(
    [
        shutil.which("npm") or "npm",
        "install",
        "--package-lock-only",
        "--ignore-scripts",
        "--no-audit",
        "--no-fund",
    ],
    cwd=base,
    check=True,
)
lock = json.loads((base / "package-lock.json").read_text())
for folder in (ROOT / "benchmarks").glob("ts-*"):
    lock["name"] = folder.name
    lock["packages"][""]["name"] = folder.name
    (folder / "package-lock.json").write_text(
        json.dumps(lock, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
for path in (ROOT / "benchmarks").rglob("*"):
    if path.is_file():
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
