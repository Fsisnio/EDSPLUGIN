from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, PostgresDsn, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration using environment variables.

    This configuration is intentionally split into:
    - Core API behavior
    - DHS compliance behavior
    - Security & auth
    - Optional metadata database (PostgreSQL)
    - Optional billing/SaaS settings (Stripe, multi-tenant)
    """

    # -------------------------------------------------------------------------
    # Core application
    # -------------------------------------------------------------------------
    PROJECT_NAME: str = "DHS Hybrid Plugin Platform"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = Field(default_factory=list)

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):  # type: ignore[override]
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # -------------------------------------------------------------------------
    # DHS compliance
    # -------------------------------------------------------------------------
    # No permanent microdata storage: toggle to enforce in-process/session-only.
    DHS_ALLOW_PERSISTENT_MICRODATA: bool = False
    # Temporary directory for per-session processing (cleaned automatically).
    TEMP_DATA_DIR: str = "/tmp/edhs_core_sessions"
    # Session TTL in seconds for in-memory/session data.
    SESSION_TTL_SECONDS: int = 60 * 60  # 1 hour

    # -------------------------------------------------------------------------
    # Security & auth (JWT, API keys, multi-tenant)
    # -------------------------------------------------------------------------
    SECRET_KEY: str = Field(
        "CHANGE_ME_IN_PRODUCTION",
        description="Symmetric key for JWT signing; override in production.",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Basic multi-tenant concept; actual tenant separation handled at app level.
    DEFAULT_TENANT_ID: str = "default"

    # API keys (optional): comma-separated list of valid keys for X-API-Key header.
    # If set, requests sending X-API-Key must use a key in this list.
    API_KEYS: Optional[str] = None

    # -------------------------------------------------------------------------
    # Optional PostgreSQL metadata database
    # -------------------------------------------------------------------------
    METADATA_DATABASE_URL: Optional[PostgresDsn] = None

    # -------------------------------------------------------------------------
    # Stripe / billing (metadata only, no microdata)
    # -------------------------------------------------------------------------
    STRIPE_API_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # -------------------------------------------------------------------------
    # DHS Program API (api.dhsprogram.com)
    # -------------------------------------------------------------------------
    # API key from https://api.dhsprogram.com/ (required for indicators, data, countries)
    DHS_PROGRAM_API_KEY: Optional[str] = None

    # -------------------------------------------------------------------------
    # Spatial data configuration
    # -------------------------------------------------------------------------
    # Root directory for admin boundary datasets (GeoPackage/shapefile).
    # Files are expected to be organized by country code and admin level.
    # Example: {ADMIN_BOUNDARIES_ROOT}/{country_code}/ADM{level}.gpkg
    ADMIN_BOUNDARIES_ROOT: str = "/opt/edhs/admin_boundaries"

    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Return singleton Settings instance.

    Using lru_cache ensures configuration is loaded once and reused,
    which is safe because configuration is read-only at runtime.
    """

    return Settings()


settings = get_settings()
