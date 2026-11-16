import io
import json
import re
import tarfile
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

from .security import SetupError, safe_relative, source_files


def github_repo(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or parsed.fragment:
        raise SetupError("Use a public HTTPS URL in the form https://github.com/owner/repository")
    match = re.fullmatch(r"/([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", parsed.path)
    if not match:
        raise SetupError("Use the repository root URL, without a branch or file path")
    return "/".join(match.groups())


def extract_archive(blob, destination: Path, max_bytes):
    total, count = 0, 0
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
        for item in archive:
            parts = item.name.split("/", 1)
            if len(parts) != 2 or not parts[1] or item.isdir():
                continue
            name = parts[1]
            if (
                any(p in {"..", ".", ""} for p in name.split("/"))
                or "\\" in name
                or ":" in name
                or name.startswith("/")
            ):
                raise SetupError("Archive contains an unsafe path")
            # Git metadata and dotfiles are unnecessary for the constrained runner.
            if name == ".gitmodules" or name == ".lfsconfig":
                raise SetupError("Submodules and Git LFS are unsupported in v1")
            if any(p.startswith(".") for p in name.split("/")):
                if name == ".gitattributes":
                    data = archive.extractfile(item).read() if item.isfile() else b""
                    if b"filter=lfs" in data:
                        raise SetupError("Git LFS repositories are unsupported in v1")
                continue
            path = safe_relative(name)
            if not item.isfile():
                raise SetupError("Repository links and special files are unsupported")
            total += item.size
            count += 1
            if total > max_bytes or count > 4000 or item.size > 2 * 1024 * 1024:
                raise SetupError("Repository exceeds file count, file size, or unpacked size limit")
            content = archive.extractfile(item).read()
            if content.startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise SetupError("Git LFS files are unsupported")
            target = destination / str(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)


def validate_profile(root, profile):
    if profile == "python":
        if not (root / "requirements.txt").is_file() or not (root / "requirements.lock").is_file():
            raise SetupError(
                "Python requires requirements.txt and a pip --require-hashes compatible requirements.lock; put code in src/ and tests in tests/"
            )
        for line in (root / "requirements.lock").read_text().splitlines():
            if (
                line.strip()
                and not line.lstrip().startswith(("#", "--hash"))
                and not re.match(r"^[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+(?:\s|$)", line.strip())
            ):
                raise SetupError(
                    "requirements.lock permits pinned PyPI packages with hashes only, no URLs or pip options"
                )
    else:
        if not (root / "package.json").is_file() or not (root / "package-lock.json").is_file():
            raise SetupError(
                "TypeScript requires package.json and package-lock.json; use Vitest tests under tests/ and code in src/"
            )
        manifest = json.loads((root / "package.json").read_text())
        lock = json.loads((root / "package-lock.json").read_text())
        deps = manifest.get("devDependencies", {}) | manifest.get("dependencies", {})
        if "vitest" not in deps or "typescript" not in deps or lock.get("lockfileVersion", 0) < 2:
            raise SetupError(
                "TypeScript requires locked vitest and typescript dependencies (npm lockfile v2+)"
            )
        for package in lock.get("packages", {}).values():
            resolved = package.get("resolved", "")
            if package.get("link") or (resolved and not resolved.startswith("https://registry.npmjs.org/")):
                raise SetupError("Only npm registry dependencies are supported, without linked packages")
    if not (root / "tests").is_dir():
        raise SetupError("Add a tests/ directory; existing tests remain protected from patches")
    source_files(root, profile)


async def import_github(url, ref, root, profile, max_mb=20):
    repo = github_repo(url)
    maximum = max_mb * 1024 * 1024
    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=False,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "DiffTrial/0.1"},
        ) as client:
            response = await client.get(f"https://api.github.com/repos/{repo}")
            if response.status_code != 200 or response.json().get("private", True):
                raise SetupError(
                    "Public repository could not be verified; check the URL or GitHub rate limit"
                )
            if response.json().get("size", 0) > max_mb * 1024:
                raise SetupError("Repository exceeds the configured size limit")
            commit = await client.get(f"https://api.github.com/repos/{repo}/commits/{quote(ref, safe='')}")
            if commit.status_code != 200:
                raise SetupError("Could not resolve the requested ref to a commit")
            sha = commit.json()["sha"]
            if not re.fullmatch(r"[0-9a-f]{40}", sha):
                raise SetupError("GitHub returned an invalid commit")
            blob = bytearray()
            async with client.stream("GET", f"https://codeload.github.com/{repo}/tar.gz/{sha}") as archive:
                archive.raise_for_status()
                async for chunk in archive.aiter_bytes():
                    blob.extend(chunk)
                    if len(blob) > maximum:
                        raise SetupError("Compressed repository exceeds the configured size limit")
            extract_archive(blob, root, maximum)
            validate_profile(root, profile)
            return {
                "kind": "github",
                "repository": f"https://github.com/{repo}",
                "commit": sha,
                "version": sha,
                "evaluation": "existing_tests_only",
            }
    except (httpx.HTTPError, KeyError, ValueError, tarfile.TarError) as exc:
        raise SetupError(
            "Import failed: check repository availability, archive and runner manifests"
        ) from exc
