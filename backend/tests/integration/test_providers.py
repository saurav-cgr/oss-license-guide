"""Integration tests for the LLM provider boundary.

Provider calls are exercised through the FastAPI boundary. The external HTTP
transport is replaced with recorded non-secret fixtures or simulated failures so
tests stay deterministic and offline while exercising the real adapters and
explanation validation.
"""

import json

import pytest
from fastapi.testclient import TestClient

from oss_license_guide.api.app import create_app
from oss_license_guide.config.settings import Settings
from oss_license_guide.providers.http import HttpResponse
from oss_license_guide.providers.protocol import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def settings(monkeypatch) -> Settings:
    instance = Settings()
    monkeypatch.setattr("oss_license_guide.api.analyses.get_settings", lambda: instance)
    return instance


def gemini_ok(explanation: str = "A clear, source-backed explanation.") -> HttpResponse:
    text = json.dumps({"explanation": explanation})
    return HttpResponse(
        200,
        json.dumps(
            {
                "candidates": [{"content": {"parts": [{"text": text}]}}],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
            }
        ).encode(),
    )


def openai_ok(explanation: str = "A clear, source-backed explanation.") -> HttpResponse:
    return HttpResponse(
        200,
        json.dumps(
            {
                "choices": [{"message": {"content": json.dumps({"explanation": explanation})}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 7},
            }
        ).encode(),
    )


def request_body(provider: str | None = "gemini", model: str | None = "gemini-2.0-flash") -> dict:
    return {
        "expression": "MIT",
        "provider": provider,
        "model": model,
        "facts": {"action": "use", "distribution": False},
    }


def test_providers_endpoint_lists_allowlisted_providers(client: TestClient) -> None:
    body = client.get("/api/v1/providers").json()
    ids = [provider["id"] for provider in body["providers"]]
    assert "gemini" in ids
    assert "openai" in ids
    assert body["providers"][0]["models"]


def test_gemini_happy_path_returns_explanation(client: TestClient, monkeypatch) -> None:
    calls: list[tuple[str, dict, dict]] = []

    def fake_post_json(url, headers, payload, timeout):
        calls.append((url, headers, payload))
        return gemini_ok()

    monkeypatch.setattr("oss_license_guide.providers.http.post_json", fake_post_json)

    response = client.post(
        "/api/v1/analyses",
        json=request_body("gemini", "gemini-2.0-flash"),
        headers={"X-Model-Key": "sk-user-key"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["explanation"] == "A clear, source-backed explanation."
    assert body["provider_note"] == ""
    url, headers, _ = calls[0]
    assert url.startswith("https://generativelanguage.googleapis.com/v1beta/models/")
    assert headers["x-goog-api-key"] == "sk-user-key"
    # The deterministic findings remain authoritative in the same response.
    assert body["outcome"] == "Likely permitted under stated assumptions"


def test_openai_happy_path_returns_explanation(client: TestClient, monkeypatch) -> None:
    calls: list[tuple[str, dict, dict]] = []

    def fake_post_json(url, headers, payload, timeout):
        calls.append((url, headers, payload))
        return openai_ok()

    monkeypatch.setattr("oss_license_guide.providers.http.post_json", fake_post_json)

    response = client.post(
        "/api/v1/analyses",
        json=request_body("openai", "gpt-4o-mini"),
        headers={"X-Model-Key": "sk-user-key"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["explanation"] == "A clear, source-backed explanation."
    url, headers, payload = calls[0]
    assert url.startswith("https://api.openai.com/v1/chat/completions")
    assert headers["Authorization"] == "Bearer sk-user-key"
    assert payload["response_format"] == {"type": "json_object"}


def test_missing_key_returns_deterministic_without_network(
    client: TestClient, monkeypatch, settings
) -> None:
    settings.gemini_api_key = "dev-secret-key"
    called: list[str] = []

    def fake_post_json(url, headers, payload, timeout):
        called.append(url)
        return gemini_ok()

    monkeypatch.setattr("oss_license_guide.providers.http.post_json", fake_post_json)

    response = client.post("/api/v1/analyses", json=request_body("gemini"))
    body = response.json()
    assert body["explanation"] == ""
    assert "API key" in body["provider_note"]
    assert called == [], "no network call and no dev-key fallback on the public path"


def test_allowlist_rejects_unknown_provider_without_network(
    client: TestClient, monkeypatch
) -> None:
    called: list[str] = []

    def fake_post_json(url, headers, payload, timeout):
        called.append(url)
        return gemini_ok()

    monkeypatch.setattr("oss_license_guide.providers.http.post_json", fake_post_json)

    response = client.post(
        "/api/v1/analyses",
        json=request_body("evil-provider", "x"),
        headers={"X-Model-Key": "sk-user-key"},
    )
    body = response.json()
    assert body["explanation"] == ""
    assert "not available" in body["provider_note"]
    assert called == []


def test_arbitrary_base_url_is_never_used(client: TestClient, monkeypatch) -> None:
    calls: list[str] = []

    def fake_post_json(url, headers, payload, timeout):
        calls.append(url)
        return gemini_ok()

    monkeypatch.setattr("oss_license_guide.providers.http.post_json", fake_post_json)

    body = request_body("gemini", "gemini-2.0-flash")
    body["base_url"] = "https://evil.example.com"
    response = client.post(
        "/api/v1/analyses",
        json=body,
        headers={"X-Model-Key": "sk-user-key"},
    )
    assert response.json()["explanation"] == "A clear, source-backed explanation."
    assert calls[0].startswith("https://generativelanguage.googleapis.com/v1beta/")
    assert "evil.example.com" not in calls[0]


@pytest.mark.parametrize(
    "exc",
    [
        ProviderAuthError("Provider rejected the credential (401)"),
        ProviderRateLimitError("Provider rate limit reached (429)"),
        ProviderTimeoutError("Provider request timed out"),
        ProviderUnavailableError("Provider returned an error (400)"),
    ],
)
def test_provider_failures_degrade_to_deterministic(
    client: TestClient, monkeypatch, exc
) -> None:
    def fake_post_json(url, headers, payload, timeout):
        raise exc

    monkeypatch.setattr("oss_license_guide.providers.http.post_json", fake_post_json)

    response = client.post(
        "/api/v1/analyses",
        json=request_body("gemini"),
        headers={"X-Model-Key": "sk-user-key"},
    )
    body = response.json()
    assert body["explanation"] == ""
    assert "deterministic" in body["provider_note"]
    # The deterministic answer is always present.
    assert body["outcome"] == "Likely permitted under stated assumptions"


def test_invalid_output_gets_one_repair_then_succeeds(
    client: TestClient, monkeypatch
) -> None:
    calls = {"count": 0}

    def fake_post_json(url, headers, payload, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            return HttpResponse(200, b"this is not json")
        return gemini_ok()

    monkeypatch.setattr("oss_license_guide.providers.http.post_json", fake_post_json)

    response = client.post(
        "/api/v1/analyses",
        json=request_body("gemini"),
        headers={"X-Model-Key": "sk-user-key"},
    )
    body = response.json()
    assert body["explanation"] == "A clear, source-backed explanation."
    assert calls["count"] == 2, "exactly one repair attempt"


def test_injected_claims_are_blocked(client: TestClient, monkeypatch) -> None:
    def fake_post_json(url, headers, payload, timeout):
        injected = json.dumps(
            {"explanation": "looks fine", "obligations": [{"text": "malicious obligation"}]}
        )
        return HttpResponse(
            200,
            json.dumps({"candidates": [{"content": {"parts": [{"text": injected}]}}]}).encode(),
        )

    monkeypatch.setattr("oss_license_guide.providers.http.post_json", fake_post_json)

    response = client.post(
        "/api/v1/analyses",
        json=request_body("gemini"),
        headers={"X-Model-Key": "sk-user-key"},
    )
    body = response.json()
    assert body["explanation"] == ""
    assert body["provider_note"] != ""
    # No generated content reached the deterministic obligations.
    obligations = [claim["text"] for claim in body["obligations"]]
    assert not any("malicious" in text for text in obligations)
