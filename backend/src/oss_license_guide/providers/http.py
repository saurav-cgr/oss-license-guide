"""Small stdlib HTTP JSON client for provider adapters.

Uses ``urllib`` so no runtime dependency is required. Secrets passed in headers
are never returned in error messages; request payloads and responses carry no
credentials. Errors are mapped to the provider protocol's error taxonomy.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from oss_license_guide.providers.protocol import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

_REDACTED = "[REDACTED]"


def _origin(url: str) -> tuple[str, str, int | None]:
    """Return the (scheme, hostname, port) origin of ``url``."""
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme, (parsed.hostname or "").lower(), parsed.port


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow only same-origin redirects; refuse credential-carrying hops.

    A cross-origin redirect would let a different host (or a plaintext
    downgrade) receive the ``Authorization`` or ``x-goog-api-key`` header
    copied onto the redirected request. Refusing such redirects prevents that
    credential leak while still allowing same-origin moves.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Any:
        if _origin(req.full_url) != _origin(newurl):
            raise ProviderUnavailableError(
                "Provider redirected to a different origin; refusing to forward credentials"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


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

    Header credentials (for example ``Authorization`` or ``x-goog-api-key``)
    are sent on the wire so provider authentication actually works. Secrets
    are never echoed: error messages derive from the response body only and are
    truncated. The caller is responsible for supplying only the configured,
    server-controlled ``url``.
    """
    data = json.dumps(payload).encode("utf-8")
    # A JSON body requires an explicit JSON content type. urllib would otherwise
    # default to application/x-www-form-urlencoded, which provider APIs reject
    # with a 400 "Invalid JSON payload" error.
    headers = dict(headers)
    headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    opener = urllib.request.build_opener(_SameOriginRedirectHandler())

    try:
        with opener.open(request, timeout=timeout) as response:
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
