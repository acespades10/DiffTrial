import pytest
from difftrial.benchmarks import prepare_benchmark
from difftrial.db import Run, Store, Task
from difftrial.schemas import ProviderConfig


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("DIFFTRIAL_DATA", str(tmp_path))
    return Store(tmp_path / "test.sqlite")


@pytest.fixture
def config():
    return ProviderConfig(endpoint="https://provider.example/v1", model="test-model")


@pytest.fixture
def queued(store, tmp_path, config):
    def make(benchmark="py-intervals"):
        from difftrial.config import Limits
        from difftrial.db import uid

        ident = uid()
        item, source = prepare_benchmark(benchmark, tmp_path / "tasks" / ident)
        with store.session() as s:
            task = Task(
                id=ident, title=item["title"], issue=item["issue"], profile=item["profile"], source=source
            )
            s.add(task)
            s.flush()
            run = Run(task_id=task.id, provider=config.model_dump(), limits=Limits().model_dump())
            s.add(run)
            s.flush()
            return run.id

    return make
