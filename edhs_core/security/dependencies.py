from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from jose import JWTError

from ..config import settings
from .auth import decode_access_token


def get_bearer_token(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> Optional[str]:
    """
    Extract a Bearer token from the Authorization header if present.
    """

    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def get_optional_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> Optional[str]:
    """
    Validate X-API-Key header when API_KEYS is configured.
    If the header is present and invalid, raises 401. If absent or API_KEYS
    is not set, returns None (no API key auth required).
    """
    if not settings.API_KEYS:
        return None
    allowed = [k.strip() for k in settings.API_KEYS.split(",") if k.strip()]
    if not allowed:
        return None
    if not x_api_key:
        return None
    if x_api_key in allowed:
        return x_api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key.",
    )


def get_current_tenant(
    request: Request,
    token: Optional[str] = Depends(get_bearer_token),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
) -> str:
    """
    Resolve the current tenant ID from JWT or header.

    Priority:
    1. `tenant_id` claim in JWT access token (if provided)
    2. `X-Tenant-ID` header
    3. Application default tenant
    """

    tenant_id = settings.DEFAULT_TENANT_ID

    if token:
        try:
            payload = decode_access_token(token)
            token_tenant_id = payload.get("tenant_id")
            if token_tenant_id:
                tenant_id = token_tenant_id
        except JWTError:
            # Invalid token; treat as unauthenticated tenant context
            pass

    if x_tenant_id:
        tenant_id = x_tenant_id

    # Attach to request state for downstream logging/monitoring
    request.state.tenant_id = tenant_id
    return tenant_id


async def require_active_subscription(
    tenant_id: str = Depends(get_current_tenant),
) -> None:
    """
    Dependency placeholder to enforce active subscription.

    For now, this is a stub always allowing requests. In a production
    SaaS environment, this should:
    - Look up the tenant in the metadata database
    - Check subscription status (via Stripe customer/subscription data)
    - Enforce limits (requests per minute, concurrent sessions, etc.)
    """

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant context is required.",
        )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers for security-related errors.
    """

    @app.exception_handler(JWTError)
    async def jwt_error_handler(_: Request, exc: JWTError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid authentication credentials."},
        )
