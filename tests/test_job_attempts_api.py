"""Tests for the JobAttempt API endpoints (GET)."""

import pytest


# =========================================================================
# GET /api/attempts/{attempt_id} – Read one attempt
# =========================================================================

class TestGetJobAttemptById:
    """GET /api/attempts/{attempt_id}"""

    def test_get_attempt_by_id(self, client, create_job_run, db_session):
        """Creating a run also creates the first QUEUED attempt (attempt_number=1)."""
        from app.db.models import JobAttempts

        run = create_job_run()
        # Look up the attempt that was created alongside the run
        attempt = (
            db_session.query(JobAttempts)
            .filter(JobAttempts.run_id == run["id"])
            .first()
        )
        assert attempt is not None

        resp = client.get(f"/api/attempts/{attempt.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == attempt.id
        assert data["run_id"] == run["id"]
        assert data["attempt_number"] == 1
        assert data["status"] == "QUEUED"

    def test_get_attempt_not_found(self, client):
        resp = client.get("/api/attempts/999999")
        assert resp.status_code == 404


# =========================================================================
# GET /api/runs/{run_id}/attempts – List attempts for a run
# =========================================================================

class TestListJobAttempts:
    """GET /api/runs/{run_id}/attempts"""

    def test_list_attempts_for_run(self, client, create_job_run):
        run = create_job_run()
        resp = client.get(f"/api/runs/{run['id']}/attempts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        # The first attempt created with the run
        first = data["items"][0]
        assert first["attempt_number"] == 1
        assert first["status"] == "QUEUED"

    def test_list_attempts_pagination(self, client, create_job_run):
        run = create_job_run()
        resp = client.get(
            f"/api/runs/{run['id']}/attempts",
            params={"page": 1, "page_size": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_size"] == 1
        assert len(data["items"]) <= 1

    def test_list_attempts_nonexistent_run(self, client):
        resp = client.get("/api/runs/999999/attempts")
        assert resp.status_code == 404
