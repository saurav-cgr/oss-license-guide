"""Thin HTTP routes for the backend API."""

from oss_license_guide.api.health import router as health_router

__all__ = ["health_router"]
