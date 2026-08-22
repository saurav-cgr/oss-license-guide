"""Application settings loaded from environment variables.

Settings are validated by pydantic-settings. Secrets never belong here;
provider credentials are handled in request memory elsewhere.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application configuration."""

    model_config = SettingsConfigDict(env_prefix="OLG_", extra="ignore")

    app_name: str = "Open Source License Information Assistant"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"

    # Comma-separated list of allowed CORS origins. Empty disables CORS.
    cors_origins: str = ""

    # Comma-separated list of allowlisted provider identifiers served by
    # GET /api/v1/providers and accepted by the analysis endpoint.
    providers_enabled: str = "gemini,openai"

    # Server-controlled provider endpoints. Public requests may select a
    # provider and model but never supply an arbitrary base URL.
    gemini_endpoint: str = "https://generativelanguage.googleapis.com/v1beta"
    openai_endpoint: str = "https://api.openai.com/v1"

    # Development-only provider key. Never used on the public path; a public
    # request without a user credential gets deterministic output instead.
    gemini_api_key: str = ""

    # When true, a missing user key may fall back to the development key.
    # Default off; public deployments must not enable this.
    allow_dev_provider_key: bool = False

    # Bounded provider call limits.
    provider_timeout_seconds: float = 10.0
    provider_max_tokens: int = 600
    provider_max_repairs: int = 1
    provider_max_output_chars: int = 2000

    @property
    def allowed_cors_origins(self) -> list[str]:
        """Split the raw CORS setting into a list, ignoring empty entries."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_providers(self) -> list[str]:
        """Split the raw provider allowlist into a list, ignoring empty entries."""
        return [item.strip() for item in self.providers_enabled.split(",") if item.strip()]

    def endpoint_for(self, provider: str) -> str | None:
        """Return the server-controlled endpoint for ``provider`` or None."""
        if provider == "gemini":
            return self.gemini_endpoint
        if provider == "openai":
            return self.openai_endpoint
        return None


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance shared across the process."""
    return Settings()
