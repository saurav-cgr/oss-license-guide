"""Integration tests for API error taxonomy and OpenAPI contract."""

from fastapi.testclient import TestClient

from oss_license_guide.api.app import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_invalid_action_returns_structured_422() -> None:
    response = client().post(
        "/api/v1/analyses",
        json={"expression": "MIT", "facts": {"action": "not-a-real-action", "distribution": False}},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"]
    # No stack traces or secrets leak into the response.
    text = response.text
    assert "Traceback" not in text
    assert 'File "' not in text


def test_invalid_recipient_returns_422() -> None:
    response = client().post(
        "/api/v1/analyses",
        json={"expression": "MIT", "facts": {"recipient": "aliens"}},
    )
    assert response.status_code == 422


def test_oversized_expression_returns_422() -> None:
    response = client().post(
        "/api/v1/analyses",
        json={"expression": "A" * 501, "facts": {}},
    )
    assert response.status_code == 422


def test_empty_expression_returns_422() -> None:
    response = client().post("/api/v1/analyses", json={"expression": "", "facts": {}})
    assert response.status_code == 422


def test_valid_request_still_succeeds() -> None:
    response = client().post(
        "/api/v1/analyses",
        json={"expression": "MIT", "facts": {"action": "use", "distribution": False}},
    )
    assert response.status_code == 200
    assert response.json()["outcome"]


def test_openapi_exposes_versioned_paths() -> None:
    response = client().get("/api/v1/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/analyses" in paths
    assert "/api/v1/expressions/parse" in paths
    assert "/api/v1/licenses" in paths
    assert "/api/v1/health" in paths
