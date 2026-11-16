import argparse
import json
import subprocess
import time
from pathlib import Path

from .benchmarks import catalog
from .db import Store
from .exports import compare, export_bundle
from .runner import build_runners, docker_status
from .workflow import Worker


def main():
    parser = argparse.ArgumentParser(prog="difftrial")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    commands.add_parser("build-runners")
    commands.add_parser("worker")
    commands.add_parser("serve")
    commands.add_parser("cleanup")
    export = commands.add_parser("export")
    export.add_argument(
        "--run", action="append", required=True, help="Explicitly selected run ID; repeat to include more"
    )
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "doctor":
        print(json.dumps({"docker": docker_status()}, indent=2))
    elif args.command == "build-runners":
        build_runners()
    elif args.command == "worker":
        worker = Worker(Store())
        print("DiffTrial worker ready. One active run; Ctrl+C stops the worker.", flush=True)
        try:
            while True:
                if not worker.once():
                    time.sleep(1)
        except KeyboardInterrupt:
            print("Worker stopped. An active lease will be marked interrupted after 30 seconds.")
    elif args.command == "serve":
        import uvicorn

        uvicorn.run("difftrial.api:app", host="127.0.0.1", port=8000)
    elif args.command == "cleanup":
        if not docker_status()["available"]:
            raise SystemExit("Start Docker first")
        store = Store()
        ids = subprocess.check_output(
            ["docker", "ps", "-aq", "--filter", "label=difftrial.run"], text=True
        ).split()
        for ident in ids:
            run_id = subprocess.check_output(
                ["docker", "inspect", "--format", '{{index .Config.Labels "difftrial.run"}}', ident],
                text=True,
            ).strip()
            try:
                run = store.detail(run_id)
                active = run["status"] == "running"
            except KeyError:
                active = False
            if not active:
                subprocess.run(["docker", "rm", "-f", ident], check=True)
    else:
        store = Store()
        bundles = [export_bundle(store.detail(i)) for i in args.run]
        args.output.mkdir(parents=True, exist_ok=True)
        for bundle in bundles:
            (args.output / f"{bundle['run']['id']}.json").write_text(
                json.dumps(bundle, indent=2), encoding="utf-8"
            )
        manifest = {
            "schema_version": "difftrial.demo.v1",
            "recorded": True,
            "runs": [b["run"] for b in bundles],
            "benchmarks": catalog(),
            "comparisons": compare([b["run"] for b in bundles]),
        }
        (args.output / "index.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
