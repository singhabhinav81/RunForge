"""
Shared pytest fixtures for the RunForge test suite.

Strategy
--------
* An **in-memory SQLite** database is used so tests never touch the real
  Postgres instance.
* A single Engine / schema is created once per session (``engine`` fixture).
* Each test function gets its own ``Session`` that is rolled back after the
  test, keeping every test fully isolated.
* The FastAPI ``TestClient`` overrides the ``get_db`` dependency so that
  route-level tests use the same transactional session.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.db.database import Base
from app.db.deps import get_db
from app.api.main import app


# ---------------------------------------------------------------------------
# Engine & schema (session-scoped – created once for the whole test run)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    """Create an in-memory SQLite engine with FK enforcement."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # SQLite does not enforce FKs by default – turn them on.
    @event.listens_for(eng, "connect")
    def _enable_fks(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create every table that the models define.
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


# ---------------------------------------------------------------------------
# Session (function-scoped – each test is isolated via rollback)
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session(engine) -> Session:
    """Yield a transactional Session that is rolled back after the test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# FastAPI TestClient (function-scoped, shares the same session)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(db_session) -> TestClient:
    """
    A ``TestClient`` whose ``get_db`` dependency returns the test session,
    ensuring API tests hit the same in-memory database.
    """

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # session lifecycle is managed by the ``db_session`` fixture

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Convenience factory fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def create_team(client):
    """Return a helper that POSTs a team and returns the JSON response."""

    def _create(name: str = "Test Team", description: str | None = "A test team"):
        payload = {"name": name}
        if description is not None:
            payload["description"] = description
        resp = client.post("/api/teams", json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _create


@pytest.fixture()
def create_job(client, create_team):
    """Return a helper that creates a team, then POSTs a job under it."""

    def _create(
        *,
        team_name: str = "Job Team",
        job_name: str = "Test Job",
        executor_type: str = "sample",
        image: str = "alpine:latest",
        description: str | None = "A test job",
    ):
        team = create_team(name=team_name)
        payload = {
            "team_id": team["id"],
            "name": job_name,
            "executor_type": executor_type,
            "image": image,
        }
        if description is not None:
            payload["description"] = description
        resp = client.post("/api/jobs", json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _create


@pytest.fixture()
def create_job_run(client, create_job):
    """Return a helper that creates a team → job → run."""

    def _create(*, job_name: str = "Run Job", executor_type: str = "sample"):
        job = create_job(job_name=job_name, executor_type=executor_type)
        resp = client.post(f"/api/jobs/{job['id']}/run")
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _create
