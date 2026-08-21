"""FastAPI application factory.

HTTP concerns live here; domain decisions stay in framework-independent
modules. This module only assembles routes and middleware.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from oss_license_guide.api import (
    analyses_router,
    expressions_router,
    health_router,
    licenses_router,
)
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

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return a stable, secret-free error shape for invalid requests."""
        details = [
            {
                "field": ".".join(str(part) for part in entry["loc"]),
                "message": entry["msg"],
            }
            for entry in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": details,
                }
            },
        )

    app.include_router(health_router, prefix=app_settings.api_prefix)
    app.include_router(expressions_router, prefix=app_settings.api_prefix)
    app.include_router(licenses_router, prefix=app_settings.api_prefix)
    app.include_router(analyses_router, prefix=app_settings.api_prefix)

    return app


app = create_app()
