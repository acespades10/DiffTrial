import hashlib
import io
import json
import tarfile

import pytest
from difftrial.exports import export_bundle
from difftrial.importer import extract_archive, github_repo, validate_profile
from difftrial.schemas import Proposal
from difftrial.security import SetupError, apply_proposal, safe_relative


@pytest.mark.parametrize(
    "path",
    ["../x", "/etc/passwd", "C:/x", "src/../tests/x.py", "src\\x.py", ".env", "src//x.py", "src/./x.py"],
)
def test_unsafe_paths_rejected(path):
    with pytest.raises(SetupError):
        safe_relative(path)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",
        "https://github.com.evil/a/b",
        "https://user@github.com/a/b",
        "https://github.com/a/b/tree/main",
        "https://github.com/a/b?token=x",
        "file:///tmp/repo",
    ],
)
def test_import_url_boundary(url):
    with pytest.raises(SetupError):
        github_repo(url)


def test_patch_is_atomic_and_tests_protected(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/a.py").write_text("old\n")
    proposal = Proposal(
        summary="malicious",
        edits=[{"path": "src/a.py", "content": "new"}, {"path": "tests/test_a.py", "content": "pass"}],
    )
    with pytest.raises(SetupError):
        apply_proposal(tmp_path, proposal, "python")
    assert (tmp_path / "src/a.py").read_text() == "old\n"


@pytest.mark.parametrize(
    "name", ["src/test_code.py", "src/conftest.py", "src/foo.spec.ts", "package.json", "requirements.lock"]
)
def test_evaluation_file_protection(tmp_path, name):
    with pytest.raises(SetupError):
        apply_proposal(tmp_path, Proposal(summary="bad", edits=[{"path": name, "content": ""}]), "python")


def tar_blob(name, content=b"x", link=False):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        info = tarfile.TarInfo(name)
        info.size = len(content)
        if link:
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
        tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


@pytest.mark.parametrize(
    "name,content,link",
    [
        ("root/../escape", b"x", False),
        ("root/src/link", b"x", True),
        ("root/.gitmodules", b"x", False),
        ("root/asset", b"version https://git-lfs.github.com/spec/v1", False),
        ("root/.gitattributes", b"*.zip filter=lfs", False),
    ],
)
def test_archive_rejects_traversal_links_submodules_lfs(tmp_path, name, content, link):
    with pytest.raises(SetupError):
        extract_archive(tar_blob(name, content, link), tmp_path, 1000)


def test_archive_expanded_size_limit(tmp_path):
    with pytest.raises(SetupError):
        extract_archive(tar_blob("root/large", b"x" * 1001), tmp_path, 1000)


def test_export_allowlist_redaction_checksums(store, queued, monkeypatch):
    ident = queued()
    monkeypatch.setenv("DIFFTRIAL_API_KEY", "secret-123456789")
    store.emit(
        ident,
        "role",
        summary="secret-123456789 C:\\Users\\private\\file.txt",
        private_reasoning="must not export",
    )
    result = export_bundle(store.detail(ident))
    text = json.dumps(result)
    assert "secret-123456789" not in text
    assert "private_reasoning" not in text
    assert "Users" not in text
    assert "endpoint" not in result["run"]["provider"]
    assert "key_env" not in result["run"]["provider"]
    for artifact in result["artifacts"]:
        assert hashlib.sha256(artifact["content"].encode()).hexdigest() == artifact["sha256"]


def test_missing_lockfile_explains_setup(tmp_path):
    with pytest.raises(SetupError, match="requirements.lock"):
        validate_profile(tmp_path, "python")
