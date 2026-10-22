"""Tests for the root endpoint and application exception handlers."""

import pytest

from app.api.exceptions.base import RunForgeException
from app.api.exceptions.team import (
    TeamNotFoundException,
    DuplicateTeamNameException,
    TeamHasJobsException,
)
from app.api.exceptions.jobs import (
    JobNotFoundException,
    DuplicateJobNameException,
    JobHasRunsException,
)
from app.api.exceptions.job_runs import JobRunNotFoundException
from app.api.exceptions.job_attempts import JobAttemptNotFoundException


# =========================================================================
# Root endpoint
# =========================================================================

class TestRootEndpoint:
    """GET /api/"""

    def test_root_returns_welcome(self, client):
        resp = client.get("/api/")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Welcome to the RunForge API!"


# =========================================================================
# Exception hierarchy
# =========================================================================

class TestExceptions:
    """Verify exception classes carry the correct status codes and messages."""

    def test_base_exception(self):
        exc = RunForgeException("boom")
        assert exc.message == "boom"
        assert exc.status_code == 400

    # -- Team exceptions --
    def test_team_not_found(self):
        exc = TeamNotFoundException(42)
        assert exc.status_code == 404
        assert "42" in exc.message

    def test_duplicate_team_name(self):
        exc = DuplicateTeamNameException("Alpha")
        assert exc.status_code == 409
        assert "Alpha" in exc.message

    def test_team_has_jobs(self):
        exc = TeamHasJobsException(7)
        assert exc.status_code == 409
        assert "7" in exc.message

    # -- Job exceptions --
    def test_job_not_found(self):
        exc = JobNotFoundException(99)
        assert exc.status_code == 404
        assert "99" in exc.message

    def test_duplicate_job_name(self):
        exc = DuplicateJobNameException(1, "Extract")
        assert exc.status_code == 409
        assert "Extract" in exc.message

    def test_job_has_runs(self):
        exc = JobHasRunsException(5)
        assert exc.status_code == 409
        assert "5" in exc.message

    # -- JobRun exceptions --
    def test_job_run_not_found(self):
        exc = JobRunNotFoundException(11)
        assert exc.status_code == 404
        assert "11" in exc.message

    # -- JobAttempt exceptions --
    def test_job_attempt_not_found(self):
        exc = JobAttemptNotFoundException(22)
        assert exc.status_code == 404
        assert "22" in exc.message


# =========================================================================
# Exception handler integration (via the API)
# =========================================================================

class TestExceptionHandlerIntegration:
    """Verify that RunForgeException subclasses are rendered as JSON by the global handler."""

    def test_404_rendered_as_json(self, client):
        resp = client.get("/api/jobs/999999")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    def test_422_validation_error(self, client):
        """Pydantic validation errors should be rendered by the custom handler."""
        resp = client.post("/api/teams", json={"name": ""})
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data
