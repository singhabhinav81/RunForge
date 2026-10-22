"""Tests for the Team API endpoints (POST / GET / PUT / DELETE)."""

import pytest


# =========================================================================
# POST /api/teams – Create
# =========================================================================

class TestCreateTeam:
    """POST /api/teams"""

    def test_create_team_success(self, client):
        resp = client.post("/api/teams", json={"name": "Alpha", "description": "First team"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Alpha"
        assert data["description"] == "First team"
        assert "id" in data

    def test_create_team_without_description(self, client):
        resp = client.post("/api/teams", json={"name": "Bravo"})
        assert resp.status_code == 201
        assert resp.json()["description"] is None

    def test_create_team_duplicate_name(self, client):
        client.post("/api/teams", json={"name": "Dup"})
        resp = client.post("/api/teams", json={"name": "Dup"})
        assert resp.status_code == 409

    def test_create_team_empty_name(self, client):
        resp = client.post("/api/teams", json={"name": ""})
        assert resp.status_code == 422

    def test_create_team_missing_name(self, client):
        resp = client.post("/api/teams", json={})
        assert resp.status_code == 422

    def test_create_team_name_too_long(self, client):
        resp = client.post("/api/teams", json={"name": "x" * 101})
        assert resp.status_code == 422


# =========================================================================
# POST /api/teams/bulk – Bulk create
# =========================================================================

class TestCreateTeamsBulk:
    """POST /api/teams/bulk"""

    def test_bulk_create_teams(self, client):
        payload = [
            {"name": "Bulk A", "description": "A"},
            {"name": "Bulk B"},
        ]
        resp = client.post("/api/teams/bulk", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Bulk A"
        assert data[1]["name"] == "Bulk B"

    def test_bulk_create_empty_list(self, client):
        resp = client.post("/api/teams/bulk", json=[])
        assert resp.status_code == 201
        assert resp.json() == []


# =========================================================================
# GET /api/teams/{team_id} – Read one
# =========================================================================

class TestGetTeamById:
    """GET /api/teams/{team_id}"""

    def test_get_team_by_id(self, client, create_team):
        team = create_team(name="Charlie")
        resp = client.get(f"/api/teams/{team['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Charlie"

    def test_get_team_not_found(self, client):
        resp = client.get("/api/teams/999999")
        assert resp.status_code == 404


# =========================================================================
# GET /api/teams – List with pagination
# =========================================================================

class TestListTeams:
    """GET /api/teams"""

    def test_list_teams_default_pagination(self, client, create_team):
        for i in range(3):
            create_team(name=f"ListTeam-{i}")

        resp = client.get("/api/teams")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert isinstance(data["teams"], list)

    def test_list_teams_custom_pagination(self, client, create_team):
        for i in range(5):
            create_team(name=f"PageTeam-{i}")

        resp = client.get("/api/teams", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_size"] == 2
        assert len(data["teams"]) <= 2

    def test_list_teams_empty(self, client):
        resp = client.get("/api/teams")
        assert resp.status_code == 200
        data = resp.json()
        assert data["teams"] == []
        assert data["total"] == 0


# =========================================================================
# PUT /api/teams/{team_id} – Update
# =========================================================================

class TestUpdateTeam:
    """PUT /api/teams/{team_id}"""

    def test_update_team_name(self, client, create_team):
        team = create_team(name="OldName")
        resp = client.put(
            f"/api/teams/{team['id']}",
            json={"name": "NewName"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"

    def test_update_team_description(self, client, create_team):
        team = create_team(name="DescTeam", description="old desc")
        resp = client.put(
            f"/api/teams/{team['id']}",
            json={"name": "DescTeam", "description": "new desc"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "new desc"

    def test_update_team_not_found(self, client):
        resp = client.put(
            "/api/teams/999999",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404


# =========================================================================
# DELETE /api/teams/{team_id} – Delete
# =========================================================================

class TestDeleteTeam:
    """DELETE /api/teams/{team_id}"""

    def test_delete_team_success(self, client, create_team):
        team = create_team(name="ToDelete")
        resp = client.delete(f"/api/teams/{team['id']}")
        assert resp.status_code == 200

        # Confirm it's gone
        resp = client.get(f"/api/teams/{team['id']}")
        assert resp.status_code == 404

    def test_delete_team_not_found(self, client):
        resp = client.delete("/api/teams/999999")
        assert resp.status_code == 404
