"""FastAPI application factory.

HTTP concerns live here; domain decisions stay in framework-independent
modules. This module only assembles routes and middleware.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from oss_license_guide.api import health_router
from oss_license_guide.config.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    app_settings = settings or get_settings()

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        openapi_url=f"{app_settings.api_prefix}/openapi.json",
    )

    if app_settings.allowed_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.allowed_cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health_router, prefix=app_settings.api_prefix)

    return app


app = create_app()
