"""Thin HTTP routes for the backend API."""

from oss_license_guide.api.expressions import router as expressions_router
from oss_license_guide.api.health import router as health_router

__all__ = ["expressions_router", "health_router"]
