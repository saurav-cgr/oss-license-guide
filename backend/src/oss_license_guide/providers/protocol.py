"""Small structured-generation protocol for LLM providers.

Providers generate an explanatory layer on top of deterministic findings only.
They never decide obligations, approve rules, or create citations. The protocol
is intentionally minimal so fake and real adapters share the same contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ProviderRequest:
    """A bounded request to a model provider. Contains no secrets beyond the key."""

    provider: str
    model: str
    api_key: str
    system_prompt: str
    user_prompt: str
    max_tokens: int = 600
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class ProviderResponse:
    """A successful structured generation result."""

    provider: str
    model: str
    text: str
    token_counts: dict[str, int] = field(default_factory=dict)


class ProviderError(Exception):
    """Base class for provider adapter failures."""


class ProviderAuthError(ProviderError):
    """The credential was missing, invalid, or rejected."""


class ProviderRateLimitError(ProviderError):
    """The provider reported a rate limit."""


class ProviderTimeoutError(ProviderError):
    """The provider call exceeded the bounded timeout."""


class ProviderOutputError(ProviderError):
    """The provider returned unparseable or out-of-schema output."""


class ProviderUnavailableError(ProviderError):
    """The provider is not configured, not allowlisted, or unreachable."""


@runtime_checkable
class Provider(Protocol):
    """An adapter capable of structured generation for one vendor."""

    def generate(self, request: ProviderRequest) -> ProviderResponse:  # pragma: no cover
        """Return a structured response or raise a ProviderError subclass."""
        ...
