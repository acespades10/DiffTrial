import json
import time
import uuid
from contextlib import contextmanager

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import active_run_limit, data_dir


def uid():
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    title: Mapped[str]
    issue: Mapped[str] = mapped_column(Text)
    profile: Mapped[str]
    source: Mapped[dict] = mapped_column(JSON)
    created: Mapped[float] = mapped_column(Float, default=time.time)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    status: Mapped[str] = mapped_column(default="queued", index=True)
    stage: Mapped[str] = mapped_column(default="queued")
    outcome: Mapped[str] = mapped_column(default="not_run")
    verdict: Mapped[str] = mapped_column(default="not_reviewed")
    provider: Mapped[dict] = mapped_column(JSON)
    limits: Mapped[dict] = mapped_column(JSON)
    baseline: Mapped[dict] = mapped_column(JSON, default=dict)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    owner: Mapped[str | None] = mapped_column(nullable=True)
    heartbeat: Mapped[float | None] = mapped_column(Float, nullable=True)
    created: Mapped[float] = mapped_column(Float, default=time.time)
    started: Mapped[float | None] = mapped_column(Float, nullable=True)
    finished: Mapped[float | None] = mapped_column(Float, nullable=True)


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    number: Mapped[int]
    patch: Mapped[str] = mapped_column(Text)
    reports: Mapped[dict] = mapped_column(JSON, default=dict)
    review: Mapped[dict] = mapped_column(JSON, default=dict)


class FindingRecord(Base):
    __tablename__ = "findings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    attempt: Mapped[int]
    detail: Mapped[dict] = mapped_column(JSON)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    kind: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    created: Mapped[float] = mapped_column(Float, default=time.time)


TERMINAL = {"completed", "cancelled", "interrupted", "infrastructure_error", "failed"}


class Store:
    def __init__(self, path=None):
        self.engine = create_engine(
            f"sqlite:///{path or data_dir() / 'difftrial.sqlite'}",
            connect_args={"check_same_thread": False, "timeout": 15},
        )

        @event.listens_for(self.engine, "connect")
        def configure(connection, _):
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=15000")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self):
        with self.sessions.begin() as session:
            yield session

    def emit(self, run_id, kind, **payload):
        with self.session() as s:
            s.add(Event(run_id=run_id, kind=kind, payload=payload))

    def update(self, run_id, **values):
        with self.session() as s:
            run = s.get(Run, run_id)
            for key, value in values.items():
                setattr(run, key, value)

    def claim(self, owner, stale_seconds=30):
        now = time.time()
        with self.session() as s:
            s.execute(text("BEGIN IMMEDIATE"))
            active = 0
            for run in s.scalars(select(Run).where(Run.status == "running")):
                if (run.heartbeat or 0) < now - stale_seconds:
                    run.status, run.stage, run.finished = "interrupted", "interrupted", now
                    run.error = "Worker lease expired. Start a new run to retry."
                    s.add(Event(run_id=run.id, kind="interrupted", payload={"message": run.error}))
                else:
                    active += 1
            if active >= active_run_limit():
                return None
            run = s.scalar(select(Run).where(Run.status == "queued").order_by(Run.created).limit(1))
            if not run:
                return None
            run.status, run.owner, run.heartbeat, run.started = "running", owner, now, now
            s.add(Event(run_id=run.id, kind="claimed", payload={"message": "Worker acquired run"}))
            return run.id

    def cancel(self, run_id):
        with self.session() as s:
            run = s.get(Run, run_id)
            if not run:
                raise KeyError(run_id)
            if run.status not in TERMINAL:
                run.cancelled = True
                if run.status == "queued":
                    run.status, run.stage, run.finished = "cancelled", "cancelled", time.time()
                s.add(
                    Event(
                        run_id=run.id,
                        kind="cancellation_requested",
                        payload={"message": "Cancellation requested"},
                    )
                )

    def events(self, run_id, after=0):
        with self.session() as s:
            return [
                {"id": e.id, "kind": e.kind, "created": e.created, "payload": e.payload}
                for e in s.scalars(
                    select(Event).where(Event.run_id == run_id, Event.id > after).order_by(Event.id)
                )
            ]

    def detail(self, run_id):
        with self.session() as s:
            run = s.get(Run, run_id)
            if not run:
                raise KeyError(run_id)
            result = {
                c.name: getattr(run, c.name)
                for c in Run.__table__.columns
                if c.name not in {"owner", "heartbeat"}
            }
            task = s.get(Task, run.task_id)
            result["task"] = {c.name: getattr(task, c.name) for c in Task.__table__.columns}
            result["attempts"] = [
                {"number": a.number, "patch": a.patch, "reports": a.reports, "review": a.review}
                for a in s.scalars(select(Attempt).where(Attempt.run_id == run_id).order_by(Attempt.number))
            ]
            result["events"] = self.events(run_id)
            result["prompt_version"] = "repair-v1"
            result["rubric_version"] = "review-v1"
            return json.loads(json.dumps(result))
