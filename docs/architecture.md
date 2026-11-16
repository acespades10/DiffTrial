# Architecture and API

The React/TypeScript Vite client uses Tailwind's build integration plus a shared semantic CSS token system. Local requests go through Vite's `/api` proxy. The production demo is a separate compile mode with only static JSON reads.

FastAPI validates input through Pydantic. SQLAlchemy owns a SQLite database configured for WAL, foreign keys, and a busy timeout. Tables store tasks, runs, attempts, findings, and events. Source snapshots and sanitized bundles live under ignored `data/`; `DIFFTRIAL_DATA` overrides the location.

The API only queues work. `difftrial worker` claims a queued run under SQLite `BEGIN IMMEDIATE`, allowing one live lease across worker processes. A separate heartbeat thread renews the lease every two seconds. On a subsequent claim, a lease older than 30 seconds becomes explicitly `interrupted`, never automatically replayed. Queued cancellations are immediate; active cancellations are checked while waiting for a provider and between Docker status polls. Restart the worker to identify stale work after a crash. `difftrial cleanup` removes stopped/abandoned containers belonging to non-running DiffTrial records.

Workflow: validate source hash, set up dependencies, record baseline tests/static analysis, read bounded source files, plan, propose existing-source replacements, validate the patch boundary, request controlled checks, execute both mandatory checks, review with `review-v1`, and optionally revise once. Each patch attempt is based on the original snapshot and exports a complete unified diff. The reviewer rubric contains twelve explicit rules; it is stored in `workflow.py`. No private chain-of-thought is requested or stored.

Provider implementations share validated configuration, generation, checks, cancellation, usage and error handling. CodexLB uses a dedicated Responses adapter with SSE completion validation. Compatible APIs can use Responses or Chat Completions. Ollama uses `/api/tags` and `/api/chat`; selection is limited to installed models in the UI. Structured output is validated even if a provider has no native schema capability. Unsupported routes, incomplete streams, rate limits, malformed JSON and authentication failures are explicit errors. Cancelling a request closes the local HTTP operation; upstream billing may continue if a provider does not support server-side cancellation.

## REST v1

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/health` | Docker prerequisite status |
| GET | `/api/v1/benchmarks` | Original task catalog |
| GET / PUT | `/api/v1/providers` | Local configuration without credential values |
| POST | `/api/v1/providers/check` | Actual small generation request |
| POST | `/api/v1/providers/models` | Installed Ollama models |
| POST | `/api/v1/tasks` | Prepare a benchmark or import a pinned public repository |
| POST | `/api/v1/runs` | Persist a queued run with configuration and limits |
| GET | `/api/v1/runs` | Latest 200 runs |
| GET | `/api/v1/runs/{id}` | Full sanitized detail |
| POST | `/api/v1/runs/{id}/cancel` | Durable cancellation request |
| GET | `/api/v1/runs/{id}/events` | SSE, persisted IDs and Last-Event-ID reconnect |
| GET | `/api/v1/comparisons?ids=a,b` | Matched-source/limits comparison cohorts |
| GET | `/api/v1/runs/{id}/export` | Versioned evidence JSON |
| GET | `/api/v1/runs/{id}/artifacts/{name}` | Allowlisted artifact and SHA-256 header |

Execution statuses: queued, running, completed, cancelled, interrupted, infrastructure_error, failed. Test outcomes: not_run, fixed, passing, failing, regressed, invalid_evidence. Reviewer verdicts: not_reviewed, accept, revise, reject, uncertain. `completed` means the workflow finished, not that the issue was fixed.

Default limits are two attempts, 900 seconds per run, 300 seconds per command, 20 MiB repository input, 512 MiB RAM, and one CPU. Run/command limits are configurable in the local form; the REST schema exposes the remaining bounded limits. By default only one worker slot is active. Set `DIFFTRIAL_MAX_ACTIVE_RUNS` to 1 through 4 and start that many worker processes to change concurrency locally. Repository import limits are set on the task request; a run also enforces its own snapshot size limit.
