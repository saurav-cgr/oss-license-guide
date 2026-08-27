"""Provider registry with server-controlled allowlist enforcement.

Public requests may only select providers present in the configured allowlist.
Adapters are built from server-controlled endpoints; no public request can
supply a base URL.
"""

from __future__ import annotations

from typing import Protocol

from oss_license_guide.config.settings import Settings
from oss_license_guide.providers.gemini import GeminiAdapter
from oss_license_guide.providers.openai import OpenAIAdapter
from oss_license_guide.providers.protocol import (
    ProviderRequest,
    ProviderResponse,
    ProviderUnavailableError,
)

# Default model identifiers served to clients per provider.
DEFAULT_MODELS: dict[str, list[str]] = {
    "gemini": ["gemini-3.5-flash-lite"],
    "openai": ["gpt-4o-mini"],
}


class _ConfiguredProvider(Protocol):
    def generate(self, request: ProviderRequest) -> ProviderResponse: ...


def is_allowed(provider: str, settings: Settings) -> bool:
    """Return whether ``provider`` is in the server allowlist."""
    return provider in settings.allowed_providers


def get_adapter(provider: str, settings: Settings) -> _ConfiguredProvider:
    """Return a configured adapter for ``provider`` or raise if unavailable."""
    if not is_allowed(provider, settings):
        raise ProviderUnavailableError(f"Provider {provider!r} is not available")
    endpoint = settings.endpoint_for(provider)
    if not endpoint:
        raise ProviderUnavailableError(f"Provider {provider!r} has no configured endpoint")
    if provider == "gemini":
        return GeminiAdapter(endpoint)
    if provider == "openai":
        return OpenAIAdapter(endpoint)
    raise ProviderUnavailableError(f"Provider {provider!r} is not supported")


def available_models(provider: str) -> list[str]:
    """Return the default model identifiers for ``provider``."""
    return DEFAULT_MODELS.get(provider, [])
