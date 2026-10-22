"""Tests for the JobRun API endpoints (POST / GET / DELETE)."""

import pytest


# =========================================================================
# POST /api/jobs/{job_id}/run – Create a run
# =========================================================================

class TestCreateJobRun:
    """POST /api/jobs/{job_id}/run"""

    def test_create_job_run_success(self, client, create_job):
        job = create_job(job_name="RunableJob")
        resp = client.post(f"/api/jobs/{job['id']}/run")
        assert resp.status_code == 201
        data = resp.json()
        assert data["job_id"] == job["id"]
        assert data["status"] == "QUEUED"
        assert "id" in data
        assert "created_at" in data

    def test_create_job_run_nonexistent_job(self, client):
        resp = client.post("/api/jobs/999999/run")
        assert resp.status_code == 404

    def test_create_multiple_runs_for_same_job(self, client, create_job):
        """Multiple runs can be created for a single job."""
        job = create_job(job_name="MultiRunJob")
        r1 = client.post(f"/api/jobs/{job['id']}/run")
        r2 = client.post(f"/api/jobs/{job['id']}/run")
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]


# =========================================================================
# GET /api/runs/{run_id} – Read one run
# =========================================================================

class TestGetJobRunById:
    """GET /api/runs/{run_id}"""

    def test_get_run_by_id(self, client, create_job_run):
        run = create_job_run()
        resp = client.get(f"/api/runs/{run['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == run["id"]
        assert data["status"] == "QUEUED"

    def test_get_run_not_found(self, client):
        resp = client.get("/api/runs/999999")
        assert resp.status_code == 404


# =========================================================================
# GET /api/jobs/{job_id}/runs – List runs for a job
# =========================================================================

class TestListJobRuns:
    """GET /api/jobs/{job_id}/runs"""

    def test_list_runs_for_job(self, client, create_job):
        job = create_job(job_name="ListRunJob")
        for _ in range(3):
            client.post(f"/api/jobs/{job['id']}/run")

        resp = client.get(f"/api/jobs/{job['id']}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["job_runs"]) == 3

    def test_list_runs_pagination(self, client, create_job):
        job = create_job(job_name="PageRunJob")
        for _ in range(5):
            client.post(f"/api/jobs/{job['id']}/run")

        resp = client.get(
            f"/api/jobs/{job['id']}/runs",
            params={"page": 1, "page_size": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_size"] == 2
        assert len(data["job_runs"]) == 2
        assert data["total"] == 5

    def test_list_runs_filter_by_status(self, client, create_job):
        job = create_job(job_name="FilterRunJob")
        client.post(f"/api/jobs/{job['id']}/run")

        resp = client.get(
            f"/api/jobs/{job['id']}/runs",
            params={"status": "QUEUED"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["status"] == "QUEUED" for r in data["job_runs"])

    def test_list_runs_nonexistent_job(self, client):
        resp = client.get("/api/jobs/999999/runs")
        assert resp.status_code == 404

    def test_list_runs_empty(self, client, create_job):
        job = create_job(job_name="NoRunJob")
        resp = client.get(f"/api/jobs/{job['id']}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["job_runs"] == []


# =========================================================================
# DELETE /api/runs/{run_id} – Delete a run
# =========================================================================

class TestDeleteJobRun:
    """DELETE /api/runs/{run_id}"""

    def test_delete_run_success(self, client, create_job_run):
        """Deleting a run cascades to its child attempts and returns 204."""
        run = create_job_run()
        resp = client.delete(f"/api/runs/{run['id']}")
        assert resp.status_code == 204
        # Verify run is gone
        assert client.get(f"/api/runs/{run['id']}").status_code == 404

    def test_delete_run_not_found(self, client):
        resp = client.delete("/api/runs/999999")
        assert resp.status_code == 404


# =========================================================================
# POST /api/runs/{run_id}/cancel – Cancel (stub)
# =========================================================================

class TestCancelJobRun:
    """POST /api/runs/{run_id}/cancel"""

    def test_cancel_endpoint_exists(self, client, create_job_run):
        """The cancel endpoint is mounted; it may return 200 or null for now."""
        run = create_job_run()
        resp = client.post(f"/api/runs/{run['id']}/cancel")
        # The route exists but the handler is a stub (returns None → 200)
        assert resp.status_code == 200
