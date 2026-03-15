from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import jwt

from ..config import settings


def create_access_token(
    subject: str,
    tenant_id: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a JWT access token for a given subject and tenant.

    Only metadata about the user/tenant is encoded. No DHS microdata
    should ever be included in JWTs.
    """

    to_encode: Dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
    }
    if extra_claims:
        to_encode.update(extra_claims)

    expire = datetime.utcnow() + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Raises `JWTError` if the token is invalid or expired.
    """

    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    return payload
