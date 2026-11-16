# Execution, import and export boundaries

## Repository input

Imports use anonymous HTTPS requests to exact GitHub API and codeload hosts. No Git credential helper or authenticated clone is used. Refs resolve to immutable commits. Compressed/uncompressed sizes, individual file sizes and file counts are bounded. Archives reject traversal, links, submodules and LFS. Dotfiles are excluded after checking unsupported metadata. No archive extraction API writes arbitrary member paths.

Only existing non-test Python or TypeScript files beneath `src/` may be changed. The application validates every edit before writing any, rejects duplicate targets, binary content, traversal and protected evaluation files, and records the resulting unified diff. Tests, manifests, lockfiles and runner configuration remain protected from agent patches. Test source is withheld from model context; reported test names and runner logs are still visible.

## Docker

Trusted runner images are built from the repository's Dockerfiles, never from an imported Dockerfile. Repository code is copied through a tar stream, not a host bind mount. No Docker socket, host directory, credentials, or inherited environment is made available inside a container.

Dependencies are installed in a disposable setup container as UID 10001 with dropped capabilities, no privilege escalation, CPU/memory/process limits, and a command timeout. Setup has network access and contains no provider credentials. Python requires hashes and binary wheels; npm uses `ci --ignore-scripts` against registry-pinned dependencies. npm install scripts and project shell scripts are not executed.

Execution uses fresh containers with no network, UID 10001, all capabilities dropped, no-new-privileges, read-only root filesystems, bounded temporary storage, memory/CPU/PID limits, and wall-clock deadlines. The trusted command wrapper selects pytest, Ruff, Vitest or tsc; model text cannot choose a host shell command. Tests also have an in-container deadline, so the primary worker's failure does not remove the test timeout. Docker process exit codes override anything asserted in a report. Empty or missing reports cannot count as passing.

Containers share the Docker engine's kernel. This is an application-level isolation design, not a demonstrated defense against kernel escapes. Use a dedicated VM or disposable machine for actively hostile repositories. Setup networking is not destination-allowlisted; dependencies are still untrusted code. Repository tests can attempt to forge their own reports, so imported test passes remain limited evidence and never prove issue resolution. The protected original suite is the basis for measured benchmark fixes.

## Local API

The API binds loopback; host and origin checks reject remote browser access and DNS-rebinding hostnames. Mutations require a custom header, and no permissive CORS middleware is enabled. This is a single-user local application, not an authenticated multi-user service. Do not expose port 8000 to the internet.

## Exports

`difftrial.bundle.v1` contains an allowlisted run, source provenance, attempt diffs, measured reports, review findings, role summaries, events, and named artifact contents with SHA-256 checksums. Provider endpoints, environment variable names, worker ownership and local storage locations are omitted. Known environment-held secrets, common token patterns and local home paths are redacted before artifact hashes are computed.

Redaction cannot recognize every possible sensitive string. Publication always uses explicit run IDs, and selected JSON is reviewed before committing. The static demo never accesses the live database. Checksums establish artifact integrity, not authenticity of a provider's reasoning or proof against a malicious repository.
