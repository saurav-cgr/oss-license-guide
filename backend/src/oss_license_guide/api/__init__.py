"""Thin HTTP routes for the backend API."""

from oss_license_guide.api.analyses import router as analyses_router
from oss_license_guide.api.expressions import router as expressions_router
from oss_license_guide.api.health import router as health_router
from oss_license_guide.api.licenses import router as licenses_router
from oss_license_guide.api.providers import router as providers_router

__all__ = [
    "analyses_router",
    "expressions_router",
    "health_router",
    "licenses_router",
    "providers_router",
]
