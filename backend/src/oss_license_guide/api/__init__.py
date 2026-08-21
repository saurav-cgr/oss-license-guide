"""Thin HTTP routes for the backend API."""

from oss_license_guide.api.expressions import router as expressions_router
from oss_license_guide.api.health import router as health_router
from oss_license_guide.api.licenses import router as licenses_router

__all__ = ["expressions_router", "health_router", "licenses_router"]
