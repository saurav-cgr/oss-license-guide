"""Native Gemini structured-generation adapter.

Calls the Gemini ``generateContent`` endpoint using the server-controlled base
URL. The key travels in the ``x-goog-api-key`` header so it never appears in a
URL. Requests JSON output so both adapters share one schema validator.
"""

from __future__ import annotations

import json

from oss_license_guide.providers import http
from oss_license_guide.providers.protocol import (
    ProviderOutputError,
    ProviderRequest,
    ProviderResponse,
)


class GeminiAdapter:
    """Adapter for the Gemini generateContent endpoint."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint.rstrip("/")

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        url = f"{self.endpoint}/models/{request.model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": request.user_prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "maxOutputTokens": request.max_tokens,
                "temperature": 0.0,
            },
        }
        response = http.post_json(
            url,
            headers={"x-goog-api-key": request.api_key},
            payload=payload,
            timeout=request.timeout_seconds,
        )
        try:
            data = response.json()
        except ValueError as error:
            raise ProviderOutputError("Gemini returned a non-JSON response") from error
        return ProviderResponse(
            provider=request.provider,
            model=request.model,
            text=_extract_text(data),
            token_counts=_token_counts(data),
        )


def _extract_text(data: dict) -> str:
    try:
        candidates = data["candidates"]
        parts = candidates[0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts).strip()
    except (KeyError, IndexError, TypeError) as error:
        raise ProviderOutputError("Gemini returned an unexpected response shape") from error


def _token_counts(data: dict) -> dict[str, int]:
    usage = data.get("usageMetadata") or {}
    counts: dict[str, int] = {}
    if usage.get("promptTokenCount") is not None:
        counts["prompt_tokens"] = int(usage["promptTokenCount"])
    if usage.get("candidatesTokenCount") is not None:
        counts["completion_tokens"] = int(usage["candidatesTokenCount"])
    return counts


def parse_json(text: str) -> dict:
    """Parse Gemini JSON text, tolerating a fenced code block."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ProviderOutputError("Gemini returned invalid JSON") from error
    if not isinstance(parsed, dict):
        raise ProviderOutputError("Gemini returned a non-object value")
    return parsed
