"""Integration tests for the LLM provider boundary.

Provider calls are exercised through the FastAPI boundary. The external HTTP
transport is replaced with recorded non-secret fixtures or simulated failures so
tests stay deterministic and offline while exercising the real adapters and
explanation validation.
"""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from oss_license_guide.api.app import create_app
from oss_license_guide.config.settings import Settings
from oss_license_guide.providers.http import HttpResponse, post_json
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


def gemini_ok(
    elaboration: str = "Under the stated scenario, MIT is likely permitted.",
) -> HttpResponse:
    text = json.dumps({"elaboration": elaboration})
    return HttpResponse(
        200,
        json.dumps(
            {
                "candidates": [{"content": {"parts": [{"text": text}]}}],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
            }
        ).encode(),
    )


def openai_ok(
    elaboration: str = "Under the stated scenario, MIT is likely permitted.",
) -> HttpResponse:
    return HttpResponse(
        200,
        json.dumps(
            {
                "choices": [{"message": {"content": json.dumps({"elaboration": elaboration})}}],
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
    # The displayed explanation is assembled from deterministic fragments and
    # the screened model elaboration, never raw model claims.
    assert "Under the stated scenario, MIT is likely permitted." in body["explanation"]
    assert "Likely permitted under stated assumptions" in body["explanation"]
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
    assert "Under the stated scenario, MIT is likely permitted." in body["explanation"]
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


def test_arbitrary_base_url_is_rejected(client: TestClient, monkeypatch) -> None:
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
    # Unknown request fields are rejected outright, so a client-supplied base
    # URL can never influence the provider endpoint.
    assert response.status_code == 422
    assert calls == []


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
    assert "Under the stated scenario, MIT is likely permitted." in body["explanation"]
    assert calls["count"] == 2, "exactly one repair attempt"


def test_injected_claims_are_blocked(client: TestClient, monkeypatch) -> None:
    def fake_post_json(url, headers, payload, timeout):
        injected = json.dumps(
            {"elaboration": "looks fine", "obligations": [{"text": "malicious obligation"}]}
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
    # Forbidden keys (obligations) make the whole elaboration invalid.
    assert body["explanation"] == ""
    assert body["provider_note"] != ""
    # No generated content reached the deterministic obligations.
    obligations = [claim["text"] for claim in body["obligations"]]
    assert not any("malicious" in text for text in obligations)


def test_claim_language_in_elaboration_is_dropped(client: TestClient, monkeypatch) -> None:
    def fake_post_json(url, headers, payload, timeout):
        injected = json.dumps({"elaboration": "You must pay royalties to the author."})
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
    # The injected requirement is screened out and never displayed.
    assert "pay royalties" not in body["explanation"]
    assert "You must" not in body["explanation"]
    assert body["explanation"] == ""
    # The deterministic answer is still authoritative.
    assert body["outcome"] == "Likely permitted under stated assumptions"


def test_authorization_header_is_sent_at_transport(monkeypatch) -> None:
    """The Authorization header must reach the wire, not be stripped.

    Regression for the bug where ``post_json`` removed Authorization before
    sending, leaving every OpenAI-compatible call unauthenticated.
    """
    captured: dict[str, str] = {}
    captured["status"] = "not-called"

    import urllib.request

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return b"{}"

    class FakeOpener:
        def open(self, request, timeout=None):
            captured["authorization"] = request.get_header("Authorization")
            captured["x_goog"] = request.get_header("x-goog-api-key")
            captured["status"] = "called"
            return FakeResponse()

    monkeypatch.setattr(
        urllib.request, "build_opener", lambda *args, **kwargs: FakeOpener()
    )

    post_json(
        "https://example.test/v1/chat/completions",
        headers={"Authorization": "Bearer sk-secret", "Content-Type": "application/json"},
        payload={"model": "gpt"},
        timeout=5.0,
    )
    assert captured["status"] == "called"
    assert captured["authorization"] == "Bearer sk-secret"
    assert captured["x_goog"] is None


def test_arbitrary_model_id_is_rejected_without_network(
    client: TestClient, monkeypatch
) -> None:
    """A model not in the server allowlist must never reach the provider URL."""
    called: list[str] = []

    def fake_post_json(url, headers, payload, timeout):
        called.append(url)
        return gemini_ok()

    monkeypatch.setattr("oss_license_guide.providers.http.post_json", fake_post_json)

    response = client.post(
        "/api/v1/analyses",
        json=request_body("gemini", "arbitrary-model"),
        headers={"X-Model-Key": "sk-user-key"},
    )
    body = response.json()
    assert body["explanation"] == ""
    assert "not allowlisted" in body["provider_note"]
    assert called == []


def test_unverifiable_model_claim_is_not_appended(
    client: TestClient, monkeypatch
) -> None:
    """Free-form model text that is not derivable from findings is rejected.

    Regression: phrase blacklisting previously let "The license permits
    commercial use without attribution." through and displayed it.
    """
    def fake_post_json(url, headers, payload, timeout):
        injected = json.dumps(
            {"elaboration": "The license permits commercial use without attribution."}
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
    assert "commercial use without attribution" not in body["explanation"]
    assert body["explanation"] == ""
    assert body["provider_note"] != ""
    assert body["outcome"] == "Likely permitted under stated assumptions"


def test_cross_origin_redirect_does_not_forward_credentials() -> None:
    """A cross-origin redirect must not receive Authorization or API-key headers."""
    import http.server
    import threading
    import time

    target_hits: list[dict] = []

    class TargetHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            target_hits.append({"Authorization": self.headers.get("Authorization")})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):  # noqa: ARG002
            pass

    target = http.server.HTTPServer(("127.0.0.1", 0), TargetHandler)
    target_port = target.server_address[1]
    threading.Thread(target=target.serve_forever, daemon=True).start()

    class RedirectHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            self.send_response(307)
            self.send_header("Location", f"http://127.0.0.1:{target_port}/")
            self.end_headers()

        def log_message(self, *args):  # noqa: ARG002
            pass

    redirector = http.server.HTTPServer(("127.0.0.1", 0), RedirectHandler)
    redirect_port = redirector.server_address[1]
    threading.Thread(target=redirector.serve_forever, daemon=True).start()

    try:
        with pytest.raises(ProviderUnavailableError):
            post_json(
                f"http://127.0.0.1:{redirect_port}/v1/chat/completions",
                headers={
                    "Authorization": "Bearer sk-secret",
                    "Content-Type": "application/json",
                },
                payload={"model": "gpt"},
                timeout=5.0,
            )
        time.sleep(0.1)
        assert target_hits == [], "credentials must not be forwarded cross-origin"
    finally:
        redirector.shutdown()
        target.shutdown()


def test_remote_http_endpoint_is_rejected() -> None:
    """Plaintext remote provider endpoints must be refused at configuration."""
    with pytest.raises(ValidationError):
        Settings(gemini_endpoint="http://api.example.com/v1beta")


def test_localhost_http_endpoint_is_allowed() -> None:
    """Localhost development endpoints may use plaintext HTTP."""
    settings = Settings(gemini_endpoint="http://127.0.0.1:8000/v1beta")
    assert settings.gemini_endpoint == "http://127.0.0.1:8000/v1beta"


def test_empty_endpoint_falls_back_to_default() -> None:
    """An empty endpoint environment value must fall back to the HTTPS default."""
    settings = Settings(gemini_endpoint="")
    assert settings.gemini_endpoint.startswith("https://")
