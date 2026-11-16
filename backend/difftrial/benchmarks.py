import json
import shutil

from .config import ROOT
from .security import SetupError, tree_hash


def catalog():
    return json.loads((ROOT / "benchmarks" / "catalog.json").read_text())


def prepare_benchmark(ident, target):
    item = next((b for b in catalog() if b["id"] == ident), None)
    if not item:
        raise SetupError("Unknown benchmark; choose an ID from /api/v1/benchmarks")
    source = ROOT / "benchmarks" / ident
    shutil.copytree(source, target, dirs_exist_ok=True)
    return item, {
        "kind": "benchmark",
        "benchmark_id": ident,
        "version": item["version"],
        "tree_sha256": tree_hash(source),
        "evaluation": "protected_regression_tests",
    }
