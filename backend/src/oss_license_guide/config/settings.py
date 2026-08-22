"""Application settings loaded from environment variables.

Settings are validated by pydantic-settings. Secrets never belong here;
provider credentials are handled in request memory elsewhere.
"""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import field_validator
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

    @field_validator(
        "allow_dev_provider_key",
        "provider_timeout_seconds",
        "provider_max_tokens",
        "provider_max_repairs",
        "provider_max_output_chars",
        "gemini_endpoint",
        "openai_endpoint",
        mode="before",
    )
    @classmethod
    def _empty_env_uses_default(cls, value: object, info) -> object:
        """Treat an empty-string env value as unset.

        Compose and .env files commonly forward variables with empty defaults
        (``${VAR:-}``); without this, an empty string fails boolean/numeric
        parsing (or, for endpoints, HTTPS validation) and prevents the API from
        starting.
        """
        if value == "":
            return cls.model_fields[info.field_name].default
        return value

    @field_validator("gemini_endpoint", "openai_endpoint")
    @classmethod
    def _endpoint_uses_https(cls, value: str, info) -> str:
        """Require HTTPS provider endpoints except approved localhost dev targets.

        A plaintext HTTP endpoint would transport API keys unencrypted. Only
        localhost/loopback development endpoints may use ``http``.
        """
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        local = host in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not local:
            raise ValueError(
                f"{info.field_name} must use https unless it targets a "
                "localhost development endpoint"
            )
        return value

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
