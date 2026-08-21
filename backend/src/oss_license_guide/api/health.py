"""Liveness and non-secret dependency status endpoint."""

from fastapi import APIRouter

from oss_license_guide.config.settings import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = get_settings()) -> dict[str, str]:
    """Return liveness information that contains no secrets."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }
