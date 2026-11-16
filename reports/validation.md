# DiffTrial validation

Validation date: 2026-11-17 (Asia/Singapore). Results describe the original benchmark suite and the selected evidence shipped with this repository.

## Application checks

| Check | Result | Evidence |
| --- | --- | --- |
| Backend unit/integration tests without Docker | 59 passed; 16 Docker cases deselected | `pytest -m 'not docker' -q` |
| Python lint | Passed | `ruff check backend tests scripts runners` |
| Frontend unit tests | 3 passed | `npm test` |
| Local and recorded TypeScript/Vite builds | Passed | `npm run build`, `npm run build:demo` |
| Local dashboard browser tests | 8 passed in Microsoft Edge on Windows | `frontend/e2e/dashboard.spec.ts` |
| Actual recorded-demo browser test | 1 passed in Microsoft Edge on Windows | `frontend/e2e-demo/recorded.spec.ts` |
| Docker integration suite | 16 passed on Linux CI at `94dc9fa` | [Checks run](https://github.com/acespades10/Agentic-Code-Review-Sandbox/actions/runs/43899610253) |
| npm dependency audit | No vulnerabilities reported | `npm audit` |
| Python dependency audit | No known vulnerabilities reported; editable local package skipped | `pip-audit` |
| Theme token contrast | 42 pairings passed; minimum normal-text ratio 4.77:1 | [contrast.json](contrast.json) |

Backend tests cover durable claims and queue restart, cancellation, stale-worker interruption, persisted event replay, malformed provider outputs and provider errors, path traversal, protected tests, atomic proposal application, source integrity, rejected proposal retention, comparison eligibility, export redaction and checksums. Docker tests cover all 12 failing-baseline-to-known-repair cases, full worker success in both languages, an unsuccessful two-attempt worker run, offline execution, non-root UID, dropped capabilities, read-only root filesystem, no host binds or Docker socket, credential exclusion and command timeout. These deterministic fixtures are not model performance measurements.

Browser tests exercise search and filters, comparison selection, attempt selection, downloads, task creation/import, settings/model discovery, cancellation, empty/loading/error/retry states, keyboard evidence tabs and skip navigation, both themes, 390/768/1024/1440px layouts, and 200% text. The recorded test loads the actual selected bundles, verifies every artifact checksum, downloads evidence, checks all 12 catalog entries and comparison groups, and asserts the absence of live creation controls. See [design delivery](design-delivery.md).

## Actual recorded runs

| Task | Baseline test exit | Patched test exit | Patched static exit | Outcome / review |
| --- | --- | --- | --- | --- |
| Python: Merge touching intervals | 1 | 0 | 0 | fixed / accept |
| TypeScript: Compare numeric versions | 1 | 0 | 0 | fixed / accept |
| Python: deliberately incomplete comment-only control | 1 | 1 | 0 | failing / reject |

The first two examples use actual CodexLB `gpt-6-astra` Responses calls for planner, implementer, validator and reviewer. The control has no model generation or model review. Its `control` provider and recorded explanation distinguish it from model failures.

Provider-reported usage totals are 4,755 tokens for the Python example and 4,351 for TypeScript. No price was configured, so no cost claim is made. Approximately 6.74s, 16.29s and 6.60s respectively describe the recorded execution intervals, not end-to-end model latency. Comparisons separate task source, limits, prompt, rubric and recording protocol. Two selected successes cannot establish a general fix rate or superiority over another provider.

The `staged_ci` protocol kept credentials on the local machine. [Baseline workflow](https://github.com/acespades10/Agentic-Code-Review-Sandbox/actions/runs/43898836063) measured the original tasks; [evaluation workflow](https://github.com/acespades10/Agentic-Code-Review-Sandbox/actions/runs/43901081596) reran baselines and tested the candidate patches. Actual reviewer calls then consumed those measured reports locally. Early planning records mention an environmental static-check failure; the evaluation rerun followed the runner cache fix and records passing baseline static checks. Historical role statements are retained rather than rewritten.

## Provider and environment status

- **CodexLB Responses:** live connection and structured generation verified; see [provider-checks.json](provider-checks.json).
- **Compatible Responses/Chat Completions:** mocked transport and error tests pass. No separate live endpoint/model/credential was configured, so live integration remains unverified.
- **Ollama:** transport tests pass. Runtime unavailable locally; live generation remains unverified and unavailable Ollama is disabled in the UI.
- **Docker:** Linux CI execution verified. Docker Desktop and WSL are absent locally, so this Windows machine cannot execute repair jobs until a Linux Docker engine is installed and running.
- **Public GitHub import:** a live `octocat/Hello-World` import correctly returned the actionable unsupported Python dependency-layout error. Supported archive handling, pinned source provenance and rejection cases are covered by automated tests; no arbitrary third-party project repair is claimed.

## Publication and limits

The repository remains private. The public [recorded demo](https://acespades10.github.io/Agentic-Code-Review-Sandbox/) contains only explicitly selected sanitized bundles and the public methodology guide. GitHub Actions links above require repository access. Routine CI has no provider secrets and never calls paid models.

Exports allowlist fields, redact recognized secrets/local paths and include SHA-256 artifact checksums. A scan of tracked files against known credential environment values found no matches. Redaction is not a guarantee against unknown secret formats; selected exports require review. Checksums establish content integrity, not independent provenance signatures.

Container boundaries reduce exposure but are not a guarantee against kernel vulnerabilities or malicious test-report forgery. Passing existing tests on an imported repository does not prove that its issue is resolved. Physical mobile devices, Windows Docker Desktop and live non-CodexLB providers were not tested.
