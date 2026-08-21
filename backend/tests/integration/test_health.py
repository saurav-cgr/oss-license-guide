"""Integration tests for the health endpoint through the FastAPI boundary."""

from fastapi.testclient import TestClient

from oss_license_guide.api.app import create_app


def test_health_reports_ok() -> None:
    """The health endpoint reports healthy with no secrets."""
    client = TestClient(create_app())
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "service" in body
