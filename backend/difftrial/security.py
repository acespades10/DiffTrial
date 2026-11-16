import difflib
import hashlib
import re
from pathlib import Path, PurePosixPath

from .schemas import Proposal


class SetupError(RuntimeError):
    pass


def safe_relative(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or ":" in name
        or path.is_absolute()
        or any(p in {"..", ".", ""} for p in name.split("/"))
    ):
        raise SetupError("Path must be a normalized relative POSIX path")
    if any(p.startswith(".") or p.endswith((" ", ".")) for p in path.parts):
        raise SetupError("Hidden and ambiguous paths are not permitted")
    return path


def editable(name, profile):
    p = safe_relative(name)
    return (
        len(p.parts) > 1
        and p.parts[0] == "src"
        and p.suffix == (".py" if profile == "python" else ".ts")
        and not any(
            re.search(r"(^|[_.-])(test|tests|spec|conftest)([_.-]|$)", part, re.I) for part in p.parts
        )
    )


def source_files(root: Path, profile):
    result = {}
    for path in sorted((root / "src").rglob("*")):
        if path.is_file() and not path.is_symlink() and editable(path.relative_to(root).as_posix(), profile):
            if path.stat().st_size <= 60000:
                result[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
        if sum(len(v) for v in result.values()) > 180000:
            raise SetupError("Source context exceeds 180 KB; narrow the repository before importing")
    if not result:
        raise SetupError("Add supported source files under src/ before importing")
    return result


def apply_proposal(root: Path, proposal: Proposal, profile: str) -> str:
    prepared, seen = [], set()
    for edit in proposal.edits:
        if not editable(edit.path, profile) or edit.path in seen:
            raise SetupError(
                "Patch may change each existing src file once; tests and configuration are protected"
            )
        seen.add(edit.path)
        path = root / edit.path
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise SetupError("Patch target must be an existing regular source file")
        if "\x00" in edit.content:
            raise SetupError("Binary patches are not supported")
        before = path.read_text(encoding="utf-8")
        after = edit.content if edit.content.endswith("\n") else edit.content + "\n"
        diff = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile="a/" + edit.path,
                tofile="b/" + edit.path,
            )
        )
        prepared.append((path, after, diff))
    if not any(diff for _, _, diff in prepared):
        raise SetupError("Patch makes no changes")
    for path, after, _ in prepared:
        path.write_text(after, encoding="utf-8", newline="\n")
    return "".join(diff for _, _, diff in prepared)


def tree_hash(root: Path):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()
