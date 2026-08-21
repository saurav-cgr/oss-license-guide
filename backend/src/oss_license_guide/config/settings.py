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

    @property
    def allowed_cors_origins(self) -> list[str]:
        """Split the raw CORS setting into a list, ignoring empty entries."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance shared across the process."""
    return Settings()
