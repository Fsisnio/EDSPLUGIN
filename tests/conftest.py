"""Pytest fixtures and configuration."""

import pytest
from fastapi.testclient import TestClient

from edhs_core.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def tenant_headers() -> dict:
    """Default tenant header for requests."""
    return {"X-Tenant-ID": "test-tenant"}


@pytest.fixture
def session_id(client: TestClient, tenant_headers: dict) -> str:
    """Create a mock session and return its session_id for use in compute/grouped/spatial tests."""
    r = client.post("/api/v1/test/mock-session", headers=tenant_headers)
    assert r.status_code == 200, r.text
    return r.json()["session_id"]
