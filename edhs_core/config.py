import json
from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, PostgresDsn, TypeAdapter, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

_cors_list_adapter = TypeAdapter(List[AnyHttpUrl])


def _parse_cors_env(raw: str) -> List[AnyHttpUrl]:
    """Accept unset/empty, comma-separated URLs, or a JSON list (pydantic-settings json-decodes only str fields)."""
    s = (raw or "").strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return _cors_list_adapter.validate_python(parsed)
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return _cors_list_adapter.validate_python(parts)


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

    # Env must be a plain str: List[...] triggers json.loads() in pydantic-settings before validators run.
    backend_cors_origins_env: str = Field(
        default="",
        validation_alias="BACKEND_CORS_ORIGINS",
        exclude=True,
    )

    @computed_field
    @property
    def BACKEND_CORS_ORIGINS(self) -> List[AnyHttpUrl]:
        return _parse_cors_env(self.backend_cors_origins_env)

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

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )


@lru_cache()
def get_settings() -> Settings:
    """Return singleton Settings instance.

    Using lru_cache ensures configuration is loaded once and reused,
    which is safe because configuration is read-only at runtime.
    """

    return Settings()


settings = get_settings()
