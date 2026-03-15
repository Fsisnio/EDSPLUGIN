"""
Structured request logging and request-id context.

Uses standard library logging. Request ID is set by middleware
and can be read from request.state.request_id for use in route handlers.
"""

import logging
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("edhs_core")


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logger for the EDHS app with a readable format."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    log = logging.getLogger("edhs_core")
    log.addHandler(handler)
    log.setLevel(level)
    log.propagate = False


def get_request_id(request: Request) -> str | None:
    """Return the request ID for this request, or None if not set."""
    return getattr(request.state, "request_id", None)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Assigns a unique request_id to each request and logs method, path, and status.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        response = await call_next(request)
        logger.info(
            "request finished method=%s path=%s status=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response
