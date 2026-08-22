"""OpenAI-compatible chat-completions structured-generation adapter.

Works with any OpenAI-compatible endpoint (including self-hosted gateways) whose
base URL is server-controlled. The key travels in the ``Authorization`` bearer
header, which the HTTP helper redacts from error details.
"""

from __future__ import annotations

import json

from oss_license_guide.providers import http
from oss_license_guide.providers.protocol import (
    ProviderOutputError,
    ProviderRequest,
    ProviderResponse,
)


class OpenAIAdapter:
    """Adapter for an OpenAI-compatible ``/chat/completions`` endpoint."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint.rstrip("/")

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        url = f"{self.endpoint}/chat/completions"
        payload = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": request.max_tokens,
            "temperature": 0.0,
        }
        response = http.post_json(
            url,
            headers={"Authorization": f"Bearer {request.api_key}"},
            payload=payload,
            timeout=request.timeout_seconds,
        )
        try:
            data = response.json()
        except ValueError as error:
            raise ProviderOutputError("OpenAI returned a non-JSON response") from error
        return ProviderResponse(
            provider=request.provider,
            model=request.model,
            text=_extract_text(data),
            token_counts=_token_counts(data),
        )


def _extract_text(data: dict) -> str:
    try:
        message = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ProviderOutputError("OpenAI returned an unexpected response shape") from error
    return str(message).strip()


def _token_counts(data: dict) -> dict[str, int]:
    usage = data.get("usage") or {}
    counts: dict[str, int] = {}
    if usage.get("prompt_tokens") is not None:
        counts["prompt_tokens"] = int(usage["prompt_tokens"])
    if usage.get("completion_tokens") is not None:
        counts["completion_tokens"] = int(usage["completion_tokens"])
    return counts


def parse_json(text: str) -> dict:
    """Parse OpenAI JSON content, tolerating a fenced code block."""
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
        raise ProviderOutputError("OpenAI returned invalid JSON") from error
    if not isinstance(parsed, dict):
        raise ProviderOutputError("OpenAI returned a non-object value")
    return parsed
