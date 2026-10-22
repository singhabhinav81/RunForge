"""Tests for the Job API endpoints (POST / GET / PUT / DELETE)."""

import pytest


# =========================================================================
# POST /api/jobs – Create
# =========================================================================

class TestCreateJob:
    """POST /api/jobs"""

    def test_create_job_success(self, client, create_team):
        team = create_team(name="JobTeam")
        payload = {
            "team_id": team["id"],
            "name": "Extract Users",
            "description": "Nightly user extract",
            "executor_type": "sample",
            "image": "alpine:latest",
        }
        resp = client.post("/api/jobs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Extract Users"
        assert data["team_id"] == team["id"]
        assert data["executor_type"] == "sample"
        assert data["image"] == "alpine:latest"

    def test_create_job_without_description(self, client, create_team):
        team = create_team(name="NoDescTeam")
        payload = {
            "team_id": team["id"],
            "name": "Minimal Job",
            "executor_type": "sample",
            "image": "alpine:latest",
        }
        resp = client.post("/api/jobs", json=payload)
        assert resp.status_code == 201
        assert resp.json()["description"] is None

    def test_create_job_team_not_found(self, client):
        payload = {
            "team_id": 999999,
            "name": "Orphan Job",
            "executor_type": "sample",
            "image": "alpine:latest",
        }
        resp = client.post("/api/jobs", json=payload)
        assert resp.status_code == 404

    def test_create_job_duplicate_name_same_team(self, client, create_team):
        team = create_team(name="DupJobTeam")
        payload = {
            "team_id": team["id"],
            "name": "SameJob",
            "executor_type": "sample",
            "image": "alpine:latest",
        }
        client.post("/api/jobs", json=payload)
        resp = client.post("/api/jobs", json=payload)
        assert resp.status_code == 409

    def test_create_job_empty_name(self, client, create_team):
        team = create_team(name="EmptyNameTeam")
        payload = {
            "team_id": team["id"],
            "name": "",
            "executor_type": "sample",
            "image": "alpine:latest",
        }
        resp = client.post("/api/jobs", json=payload)
        assert resp.status_code == 422

    def test_create_job_missing_required_fields(self, client):
        resp = client.post("/api/jobs", json={"name": "Incomplete"})
        assert resp.status_code == 422

    def test_create_job_name_too_long(self, client, create_team):
        team = create_team(name="LongNameTeam")
        payload = {
            "team_id": team["id"],
            "name": "x" * 101,
            "executor_type": "sample",
            "image": "alpine:latest",
        }
        resp = client.post("/api/jobs", json=payload)
        assert resp.status_code == 422


# =========================================================================
# GET /api/jobs/{job_id} – Read one
# =========================================================================

class TestGetJobById:
    """GET /api/jobs/{job_id}"""

    def test_get_job_by_id(self, client, create_job):
        job = create_job(job_name="FindMe")
        resp = client.get(f"/api/jobs/{job['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "FindMe"
        assert "team_name" in data

    def test_get_job_not_found(self, client):
        resp = client.get("/api/jobs/999999")
        assert resp.status_code == 404


# =========================================================================
# GET /api/jobs?team_id=... – List with pagination
# =========================================================================

class TestListJobs:
    """GET /api/jobs?team_id=..."""

    def test_list_jobs_for_team(self, client, create_team):
        team = create_team(name="ListJobTeam")
        for i in range(3):
            client.post("/api/jobs", json={
                "team_id": team["id"],
                "name": f"ListJob-{i}",
                "executor_type": "sample",
                "image": "alpine:latest",
            })

        resp = client.get("/api/jobs", params={"team_id": team["id"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["jobs"]) == 3

    def test_list_jobs_pagination(self, client, create_team):
        team = create_team(name="PageJobTeam")
        for i in range(5):
            client.post("/api/jobs", json={
                "team_id": team["id"],
                "name": f"PageJob-{i}",
                "executor_type": "sample",
                "image": "alpine:latest",
            })

        resp = client.get("/api/jobs", params={"team_id": team["id"], "page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_size"] == 2
        assert len(data["jobs"]) == 2
        assert data["total"] == 5

    def test_list_jobs_missing_team_id(self, client):
        """team_id is a required query parameter."""
        resp = client.get("/api/jobs")
        assert resp.status_code == 422

    def test_list_jobs_nonexistent_team(self, client):
        resp = client.get("/api/jobs", params={"team_id": 999999})
        assert resp.status_code == 404

    def test_list_jobs_empty_result(self, client, create_team):
        team = create_team(name="EmptyJobTeam")
        resp = client.get("/api/jobs", params={"team_id": team["id"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["jobs"] == []


# =========================================================================
# PUT /api/jobs/{job_id} – Update
# =========================================================================

class TestUpdateJob:
    """PUT /api/jobs/{job_id}"""

    def test_update_job_name(self, client, create_job):
        job = create_job(job_name="OldJob")
        resp = client.put(
            f"/api/jobs/{job['id']}",
            json={"name": "NewJob"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewJob"

    def test_update_job_image(self, client, create_job):
        job = create_job(job_name="ImgJob")
        resp = client.put(
            f"/api/jobs/{job['id']}",
            json={"image": "python:3.12"},
        )
        assert resp.status_code == 200
        assert resp.json()["image"] == "python:3.12"

    def test_update_job_not_found(self, client):
        resp = client.put(
            "/api/jobs/999999",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404

    def test_update_job_partial_fields(self, client, create_job):
        """Sending only description should leave other fields untouched."""
        job = create_job(job_name="PartialUpdate")
        resp = client.put(
            f"/api/jobs/{job['id']}",
            json={"description": "Updated description"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated description"
        assert data["name"] == "PartialUpdate"


# =========================================================================
# DELETE /api/jobs/{job_id} – Delete
# =========================================================================

class TestDeleteJob:
    """DELETE /api/jobs/{job_id}"""

    def test_delete_job_not_found(self, client):
        resp = client.delete("/api/jobs/999999")
        assert resp.status_code == 404
