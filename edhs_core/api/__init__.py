"""
API package for EDHS core.

This package exposes versioned routers and request/response schemas
for DHS/EDHS data processing. All endpoints must respect DHS
compliance rules (no permanent storage, no redistribution of data).
"""

from .routes import api_router

__all__ = ["api_router"]
