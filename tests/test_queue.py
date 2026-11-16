import time
from concurrent.futures import ThreadPoolExecutor

from difftrial.db import Run, Store


def test_queue_survives_reopening(store, queued):
    ident = queued()
    reopened = Store(store.engine.url.database)
    assert reopened.claim("new-worker") == ident
    assert reopened.detail(ident)["status"] == "running"


def test_only_one_worker_claims(store, queued):
    ids = [queued(), queued()]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(store.claim, ["a", "b"]))
    assert sum(r in ids for r in results) == 1
    assert results.count(None) == 1


def test_queued_cancellation_is_durable(store, queued):
    ident = queued()
    store.cancel(ident)
    assert store.detail(ident)["status"] == "cancelled"
    assert store.claim("worker") is None


def test_stale_worker_explicitly_interrupted(store, queued):
    first, second = queued(), queued()
    assert store.claim("dead") == first
    store.update(first, heartbeat=time.time() - 60)
    assert store.claim("replacement") == second
    assert store.detail(first)["status"] == "interrupted"
    assert any(e["kind"] == "interrupted" for e in store.events(first))


def test_running_cancellation_does_not_free_slot_before_exit(store, queued):
    first = queued()
    queued()
    store.claim("worker")
    store.cancel(first)
    with store.session() as s:
        assert s.get(Run, first).cancelled
    assert store.claim("other-worker") is None


def test_persisted_event_cursor_excludes_already_seen(store, queued):
    ident = queued()
    store.emit(ident, "first", summary="one")
    cursor = store.events(ident)[-1]["id"]
    store.emit(ident, "second", summary="two")
    reopened = Store(store.engine.url.database)
    assert [e["kind"] for e in reopened.events(ident, cursor)] == ["second"]
