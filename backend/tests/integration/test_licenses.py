"""Integration tests for SPDX catalog lookup and search through the API."""

from fastapi.testclient import TestClient

from oss_license_guide.api.app import create_app


def test_list_licenses_returns_catalog() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/licenses")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "3.24.0"
    assert body["count"] > 0
    for entry in body["licenses"]:
        assert "id" in entry
        assert "name" in entry


def test_search_returns_known_ids() -> None:
    client = TestClient(create_app())
    mit = client.get("/api/v1/licenses", params={"q": "MIT license"}).json()
    apache = client.get("/api/v1/licenses", params={"q": "apache"}).json()
    mit_ids = {entry["id"] for entry in mit["licenses"]}
    apache_ids = {entry["id"] for entry in apache["licenses"]}
    assert "MIT" in mit_ids
    assert "Apache-2.0" in apache_ids


def test_license_detail_returns_text_and_hash() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/licenses/MIT")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "MIT"
    assert body["text"]
    assert body["text_hash"]


def test_deprecated_identifier_lookup() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/licenses/GPL-2.0")
    assert response.status_code == 200
    assert response.json()["deprecated"] is True


def test_unknown_identifier_returns_404() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/licenses/Not-A-Real-License")
    assert response.status_code == 404
