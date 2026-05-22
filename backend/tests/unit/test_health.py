"""Unit tests for the /health endpoint."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from catalog_agent.api.main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    with (
        patch("catalog_agent.api.main._check_bq", return_value=True),
        patch("catalog_agent.api.main._check_lineage_api", return_value=True),
    ):
        response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["bq_reachable"] is True
    assert data["lineage_api_reachable"] is True
    assert "gcp_project" in data


def test_health_bq_unreachable() -> None:
    with (
        patch("catalog_agent.api.main._check_bq", return_value=False),
        patch("catalog_agent.api.main._check_lineage_api", return_value=False),
    ):
        response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["bq_reachable"] is False
    assert data["lineage_api_reachable"] is False


def test_health_contains_project() -> None:
    with (
        patch("catalog_agent.api.main._check_bq", return_value=True),
        patch("catalog_agent.api.main._check_lineage_api", return_value=True),
        patch(
            "catalog_agent.api.main.get_settings",
            return_value=MagicMock(
                gcp_project_id="test-project",
                lineage_location="us",
            ),
        ),
    ):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["gcp_project"] == "test-project"
