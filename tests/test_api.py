from difftrial.api import create_app
from fastapi.testclient import TestClient


def client(store):
    return TestClient(create_app(store), headers={"X-DiffTrial-Local": "1"})


def test_api_origin_guard(store):
    response = client(store).get("/api/v1/runs", headers={"Origin": "https://attacker.example"})
    assert response.status_code == 403
    response = TestClient(create_app(store)).post("/api/v1/tasks", json={"benchmark_id": "py-intervals"})
    assert response.status_code == 403


def test_api_creation_cancel_export_reconnect(store, config):
    http = client(store)
    task = http.post("/api/v1/tasks", json={"benchmark_id": "py-intervals"}).json()
    response = http.post("/api/v1/runs", json={"task_id": task["id"], "provider": config.model_dump()})
    assert response.status_code == 201
    ident = response.json()["id"]
    first = store.events(ident)[0]["id"]
    assert http.post(f"/api/v1/runs/{ident}/cancel").status_code == 200
    stream = http.get(f"/api/v1/runs/{ident}/events", headers={"Last-Event-ID": str(first)}).text
    assert "cancellation_requested" in stream
    assert '"kind": "queued"' not in stream
    assert "event: done" in stream
    assert http.get(f"/api/v1/runs/{ident}/events", headers={"Last-Event-ID": "bad"}).status_code == 422
    export = http.get(f"/api/v1/runs/{ident}/export")
    assert export.json()["schema_version"] == "difftrial.bundle.v1"
    artifact = http.get(f"/api/v1/runs/{ident}/artifacts/baseline.json")
    assert len(artifact.headers["x-artifact-sha256"]) == 64
    assert http.get(f"/api/v1/runs/{ident}/artifacts/secret.txt").status_code == 404
    assert http.get("/api/v1/runs/missing").status_code == 404


def test_invalid_import_actionable(store):
    response = client(store).post(
        "/api/v1/tasks", json={"github_url": "https://evil.example/a/b", "issue": "fix"}
    )
    assert response.status_code == 422
    assert "public HTTPS" in response.json()["detail"]
