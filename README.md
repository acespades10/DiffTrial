# DiffTrial

An agentic code repair and evaluation workbench. Agents propose changes; disposable Docker containers record what those changes actually do.

The repository keeps its original name, **Agentic-Code-Review-Sandbox**. The application is branded **DiffTrial**.

## Two experiences

- **Local workbench:** React dashboard, FastAPI API, SQLite database, separate durable worker, environment-held model credentials, and Docker execution.
- **Recorded portfolio:** a read-only GitHub Pages build containing explicitly selected, sanitized evidence bundles. It has no submission endpoint, provider settings, or hosted execution.

Runs keep **execution status**, **test outcome**, and **reviewer verdict** separate. Passing an imported repository's existing tests does not prove that its issue is resolved.

## Local setup

Requires Python 3.11+, Node 22.12+, npm, and a running **Linux Docker engine**. On Windows, use Docker Desktop configured for Linux containers; that installation has not been verified on the development machine. Ollama is optional.

```sh
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e '.[dev]'
difftrial doctor
difftrial build-runners
```

Set `CODEX_LB_API_KEY` in the backend and worker environment for CodexLB. DiffTrial reads the active CodexLB endpoint and model from your local Codex TOML configuration when available. It never reads credentials from that file or writes them into source. Alternatively configure an HTTPS endpoint and model in the local dashboard. OpenAI-compatible APIs use `OPENAI_API_KEY` or `DIFFTRIAL_API_KEY`.

Start three terminals from the repository root:

```sh
difftrial serve
difftrial worker
cd frontend && npm ci && npm run dev
```

Open http://127.0.0.1:5173. The API listens on loopback only; use the Vite proxy for the UI. The default API origins and hosts are deliberately restricted. API documentation is at http://127.0.0.1:8000/docs; mutating requests require `X-DiffTrial-Local: 1`.

Docker absence blocks execution and produces an explicit infrastructure error. Ollama absence disables only Ollama. `difftrial build-runners` downloads runner base images and tools; allow several minutes on the first run.

## Supported repositories

Public `https://github.com/owner/repository` URLs only. The importer resolves a ref to a 40-character commit and stores a content hash. v1 supports a deliberately narrow layout:

| Profile | Source | Tests | Dependencies |
| --- | --- | --- | --- |
| Python / pytest | `src/**/*.py` | `tests/` | `requirements.txt` and a hash-pinned `requirements.lock` |
| TypeScript / Vitest | `src/**/*.ts` | `tests/**/*.test.ts` | `package.json`, npm v2+ `package-lock.json`, TypeScript and Vitest |

Python dependencies must have binary wheels and PyPI hash pins. npm dependencies must resolve to the npm registry; install scripts are disabled. Projects needing install hooks, custom test configuration, external services, submodules, LFS, symlinks, or a different layout need adaptation before import. Tests and configuration cannot be patched. Read [the execution boundary](docs/security.md) before running unfamiliar code.

## Validation

```sh
pytest -m 'not docker' -q
ruff check backend tests scripts runners
cd frontend
npm test
npm run build
npm run test:e2e
# Linux: npx playwright install --with-deps chromium
# Windows browser tests use installed Microsoft Edge.
```

With Docker running and the runner images built:

```sh
pytest -m docker -q
```

Routine CI has no model credentials or paid calls. It checks both applications, the Docker boundary, twelve known benchmark repairs, and successful/unsuccessful worker paths with clearly identified deterministic test adapters. Live model calls are opt-in through `python scripts/smoke_provider.py`.

## Publishing selected runs

```sh
difftrial export --run RUN_ID --run ANOTHER_RUN_ID --output frontend/public/demo
cd frontend
npm run build:demo
```

Review the emitted JSON and artifact checksums before committing it. The Pages workflow publishes `frontend/dist` from `main`. Enable GitHub Pages with **GitHub Actions** as its build source. Free Pages requires a public repository unless the account has a plan supporting private-repository Pages.

For a machine with model access but no Docker, [staged evidence recording](docs/evidence.md) uses Docker on GitHub Actions while keeping provider credentials local. Those records explicitly identify where and when generation and execution occurred.

## Documentation

- [Architecture and API](docs/architecture.md)
- [Execution and export boundaries](docs/security.md)
- [Benchmark methodology](docs/benchmarks.md)
- [Staged evidence recording](docs/evidence.md)
- [Design decisions](DESIGN.md)
- [Validation results](reports/validation.md)
- [Design delivery checks](reports/design-delivery.md)
- [Evidence-supported portfolio wording](docs/portfolio.md)

This is an original implementation and original benchmark suite. A separate portfolio project's capability description informed the four-role concept; its code, branding, benchmarks, and reported measurements are not used here.
