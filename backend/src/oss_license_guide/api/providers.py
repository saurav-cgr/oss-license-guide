"""Configured provider choices, filtered by the server allowlist."""

from fastapi import APIRouter
from pydantic import BaseModel

from oss_license_guide.config.settings import get_settings
from oss_license_guide.providers.registry import available_models

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderInfo(BaseModel):
    id: str
    models: list[str] = []


class ProviderListResponse(BaseModel):
    providers: list[ProviderInfo] = []


@router.get("", response_model=ProviderListResponse)
def list_providers() -> ProviderListResponse:
    """Return allowlisted providers and their default models."""
    settings = get_settings()
    providers = [
        ProviderInfo(id=provider, models=available_models(provider))
        for provider in settings.allowed_providers
        if settings.endpoint_for(provider) is not None
    ]
    return ProviderListResponse(providers=providers)
