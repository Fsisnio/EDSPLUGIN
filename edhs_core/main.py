import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.dhs_routes import router as dhs_api_router
from .api.routes import api_router
from .config import settings
from .security.dependencies import register_exception_handlers
from .utils.cleanup import ensure_temp_dir, schedule_periodic_cleanup
from .utils.logging_config import RequestLoggingMiddleware, configure_logging


def create_app() -> FastAPI:
    """
    Application factory for the EDHS core engine.

    - Configures CORS
    - Registers API routers
    - Attaches security/exception handlers
    - Sets up DHS-compliant temporary storage and cleanup
    """

    app = FastAPI(
        title=settings.PROJECT_NAME,
        debug=settings.DEBUG,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    )

    # Request logging and request-id (add first so it runs last in the chain)
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    configure_logging(level=log_level)
    app.add_middleware(RequestLoggingMiddleware)

    # CORS
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(dhs_api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        """Root path: point users to the API and docs."""
        return {
            "service": settings.PROJECT_NAME,
            "api": settings.API_V1_PREFIX,
            "docs": "/docs",
            "health": f"{settings.API_V1_PREFIX}/health",
        }

    # Security & error handling
    register_exception_handlers(app)

    # Startup/shutdown events for temp directory and cleanup
    @app.on_event("startup")
    async def on_startup() -> None:
        """
        Prepare runtime environment.

        - Ensure temporary session directory exists
        - Schedule background cleanup of expired sessions/files
        """

        ensure_temp_dir(Path(settings.TEMP_DATA_DIR))
        schedule_periodic_cleanup(
            temp_dir=Path(settings.TEMP_DATA_DIR),
            ttl_seconds=settings.SESSION_TTL_SECONDS,
        )

    return app


app = create_app()
