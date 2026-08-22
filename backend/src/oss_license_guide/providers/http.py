"""Small stdlib HTTP JSON client for provider adapters.

Uses ``urllib`` so no runtime dependency is required. Secrets passed in headers
are never returned in error messages; request payloads and responses carry no
credentials. Errors are mapped to the provider protocol's error taxonomy.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from oss_license_guide.providers.protocol import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

_REDACTED = "[REDACTED]"


class HttpResponse:
    """A minimal HTTP response wrapper."""

    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body

    def json(self) -> Any:
        """Parse the body as JSON, raising ValueError on failure."""
        return json.loads(self.body.decode("utf-8"))

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> HttpResponse:
    """POST a JSON payload and return the response.

    Raises a provider error subclass for auth, rate-limit, timeout, and
    transport failures. The caller is responsible for supplying only the
    configured, server-controlled ``url``.
    """
    data = json.dumps(payload).encode("utf-8")
    safe_headers = {key: value for key, value in headers.items() if key.lower() != "authorization"}
    request = urllib.request.Request(url, data=data, headers=safe_headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResponse(response.status, response.read())
    except urllib.error.HTTPError as error:
        body = error.read()
        _raise_for_status(error.code, body)
        raise
    except urllib.error.URLError as error:
        reason = getattr(error, "reason", error)
        if isinstance(reason, TimeoutError):
            raise ProviderTimeoutError("Provider request timed out") from error
        raise ProviderUnavailableError("Provider is unreachable") from error
    except TimeoutError as error:
        raise ProviderTimeoutError("Provider request timed out") from error
    except OSError as error:
        raise ProviderUnavailableError("Provider transport error") from error


def _raise_for_status(status: int, body: bytes) -> None:
    """Map an HTTP status to the provider error taxonomy without leaking secrets.

    Raises for every non-success status so a raw HTTPError never escapes the
    provider boundary; the explanation service degrades to deterministic.
    """
    detail = _safe_detail(body)
    if status in (401, 403):
        raise ProviderAuthError(f"Provider rejected the credential ({status}){detail}")
    if status == 429:
        raise ProviderRateLimitError(f"Provider rate limit reached (429){detail}")
    if status >= 500:
        raise ProviderUnavailableError(f"Provider server error ({status}){detail}")
    raise ProviderUnavailableError(f"Provider returned an error ({status}){detail}")


def _safe_detail(body: bytes) -> str:
    """Return a short, non-secret detail snippet from an error body."""
    try:
        text = " ".join(body.decode("utf-8", errors="replace").split())
    except Exception:  # pragma: no cover - defensive
        return ""
    if not text:
        return ""
    return " - " + text[:120]


def redact(value: str | None) -> str:
    """Return a redacted placeholder when ``value`` looks like a credential."""
    if not value:
        return ""
    return _REDACTED
