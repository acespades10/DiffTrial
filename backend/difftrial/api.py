import asyncio
import json
import shutil

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import select
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .benchmarks import catalog, prepare_benchmark
from .config import active_run_limit, data_dir, local_codex_defaults
from .db import TERMINAL, Run, Store, Task, uid
from .exports import compare, export_bundle
from .importer import import_github, validate_profile
from .providers import ProviderError, adapter
from .runner import docker_status
from .schemas import ProviderConfig, RunInput, TaskInput
from .security import SetupError, tree_hash


def create_app(store=None):
    store = store or Store()
    app = FastAPI(title="DiffTrial", version="1.0.0")
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in {
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        }:
            return JSONResponse({"detail": "Only the local DiffTrial UI may access this API"}, 403)
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and request.headers.get("x-difftrial-local") != "1"
        ):
            return JSONResponse({"detail": "The X-DiffTrial-Local: 1 header is required"}, 403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(SetupError)
    async def setup_error(request, exc):
        return JSONResponse({"detail": str(exc)}, 422)

    @app.exception_handler(ProviderError)
    async def provider_error(request, exc):
        return JSONResponse({"detail": str(exc), "code": exc.code, "verified": False}, 502)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Record not found"}, 404)

    @app.get("/api/v1/health")
    def health():
        return {
            "mode": "local",
            "docker": docker_status(),
            "queue": "durable_sqlite",
            "active_run_limit": active_run_limit(),
        }

    @app.get("/api/v1/benchmarks")
    def benchmarks():
        return catalog()

    @app.get("/api/v1/providers")
    def providers():
        settings = data_dir() / "provider.json"
        endpoint, model = local_codex_defaults()
        config = (
            json.loads(settings.read_text())
            if settings.exists()
            else {
                "kind": "codexlb",
                "transport": "responses",
                "endpoint": endpoint,
                "model": model,
                "key_env": "CODEX_LB_API_KEY",
            }
        )
        return {"config": config, "credential_storage": "environment_only"}

    @app.put("/api/v1/providers")
    def save_provider(config: ProviderConfig):
        path = data_dir() / "provider.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
        return {"saved": True}

    @app.post("/api/v1/providers/check")
    async def provider_check(config: ProviderConfig):
        return await adapter(config).check()

    @app.post("/api/v1/providers/models")
    async def provider_models(config: ProviderConfig):
        return {"models": await adapter(config).models()}

    @app.post("/api/v1/tasks", status_code=201)
    async def create_task(request: TaskInput):
        task_id = uid()
        directory = data_dir() / "tasks" / task_id
        directory.mkdir(parents=True)
        try:
            if request.benchmark_id:
                item, source = prepare_benchmark(request.benchmark_id, directory)
                title, issue, profile = item["title"], item["issue"], item["profile"]
            else:
                source = await import_github(
                    request.github_url, request.ref, directory, request.profile, request.repository_mb
                )
                title, issue, profile = request.github_url.rsplit("/", 1)[-1], request.issue, request.profile
            validate_profile(directory, profile)
            source["tree_sha256"] = tree_hash(directory)
            with store.session() as s:
                s.add(Task(id=task_id, title=title, issue=issue, profile=profile, source=source))
            return {"id": task_id, "title": title, "source": source}
        except Exception:
            # The path is a server-created UUID inside the data/tasks directory.
            shutil.rmtree(directory)
            raise

    @app.post("/api/v1/runs", status_code=201)
    def create_run(request: RunInput):
        with store.session() as s:
            if not s.get(Task, request.task_id):
                raise HTTPException(404, "Task not found")
            run = Run(
                task_id=request.task_id,
                provider=request.provider.model_dump(),
                limits=request.limits.model_dump(),
            )
            s.add(run)
            s.flush()
            run_id = run.id
        store.emit(run_id, "queued", message="Waiting for the local worker")
        return store.detail(run_id)

    @app.get("/api/v1/runs")
    def runs():
        with store.session() as s:
            ids = list(s.scalars(select(Run.id).order_by(Run.created.desc()).limit(200)))
        return [export_bundle(store.detail(i))["run"] for i in ids]

    @app.get("/api/v1/runs/{run_id}")
    def detail(run_id: str):
        return export_bundle(store.detail(run_id))["run"]

    @app.post("/api/v1/runs/{run_id}/cancel")
    def cancel(run_id: str):
        store.cancel(run_id)
        return {"requested": True}

    @app.get("/api/v1/runs/{run_id}/events")
    async def events(
        run_id: str, request: Request, last_event_id: str | None = Header(default=None), after: int = 0
    ):
        store.detail(run_id)
        try:
            cursor = max(after, int(last_event_id or 0))
        except ValueError:
            raise HTTPException(422, "Last-Event-ID must be an integer") from None

        async def stream():
            nonlocal cursor
            while not await request.is_disconnected():
                for item in store.events(run_id, cursor):
                    cursor = item["id"]
                    from .exports import redact

                    yield f"id: {cursor}\nevent: progress\ndata: {json.dumps(redact(item))}\n\n"
                with store.session() as s:
                    finished = s.get(Run, run_id).status in TERMINAL
                if finished:
                    yield "event: done\ndata: {}\n\n"
                    break
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
        )

    @app.get("/api/v1/comparisons")
    def comparisons(ids: str = ""):
        selected = ids.split(",") if ids else [r["id"] for r in runs()]
        if len(selected) > 200:
            raise HTTPException(422, "Compare at most 200 runs")
        return compare([export_bundle(store.detail(i))["run"] for i in selected])

    @app.get("/api/v1/runs/{run_id}/export")
    def export(run_id: str):
        bundle = export_bundle(store.detail(run_id))
        return JSONResponse(
            bundle,
            headers={"Content-Disposition": f'attachment; filename="difftrial-{bundle["run"]["id"]}.json"'},
        )

    @app.get("/api/v1/runs/{run_id}/artifacts/{name}")
    def artifact(run_id: str, name: str):
        artifacts = export_bundle(store.detail(run_id))["artifacts"]
        item = next((a for a in artifacts if a["name"] == name), None)
        if not item:
            raise HTTPException(404, "Artifact not found")
        return Response(
            item["content"],
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="{item["name"]}"',
                "X-Artifact-SHA256": item["sha256"],
            },
        )

    return app


app = create_app()
