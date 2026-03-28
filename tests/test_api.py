"""API endpoint tests."""

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    """GET /api/v1/health returns 200 and status ok."""
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_api_root(client: TestClient) -> None:
    """GET /api/v1 returns service info and links."""
    r = client.get("/api/v1")
    assert r.status_code == 200
    data = r.json()
    assert data.get("service") == "DHS Hybrid Plugin Platform API"
    assert data.get("version") == "v1"
    assert "health" in data
    assert "indicators" in data
    assert "sessions_from_url" in data


def test_indicators_list(client: TestClient, tenant_headers: dict) -> None:
    """GET /api/v1/indicators returns registered indicators."""
    r = client.get("/api/v1/indicators", headers=tenant_headers)
    assert r.status_code == 200
    data = r.json()
    assert "indicators" in data
    ids = [i["id"] for i in data["indicators"]]
    assert "modern_contraception_rate" in ids
    assert "stunting_prevalence" in ids


def test_mock_session(client: TestClient, tenant_headers: dict) -> None:
    """POST /api/v1/test/mock-session creates a session and returns session_id."""
    r = client.post("/api/v1/test/mock-session", headers=tenant_headers)
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert "tenant_id" in data
    assert data["tenant_id"] == "test-tenant"


def test_get_session_info(client: TestClient, tenant_headers: dict, session_id: str) -> None:
    """GET /api/v1/sessions/{session_id} returns session metadata."""
    r = client.get(f"/api/v1/sessions/{session_id}", headers=tenant_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == session_id
    assert data["tenant_id"] == "test-tenant"
    assert "filename" in data


def test_get_session_404(client: TestClient, tenant_headers: dict) -> None:
    """GET /api/v1/sessions/{session_id} returns 404 for unknown session."""
    r = client.get("/api/v1/sessions/nonexistent-session-id", headers=tenant_headers)
    assert r.status_code == 404


def test_session_from_url_invalid_url(client: TestClient, tenant_headers: dict) -> None:
    """POST /api/v1/sessions/from-url returns 400 for non-http(s) URL."""
    r = client.post(
        "/api/v1/sessions/from-url",
        headers={**tenant_headers, "Content-Type": "application/json"},
        json={"dataset_url": "ftp://example.com/file.dta"},
    )
    assert r.status_code == 400
    assert "url" in r.json().get("detail", "").lower() or "http" in r.json().get("detail", "").lower()


def test_session_from_url_optional_metadata(client: TestClient, tenant_headers: dict) -> None:
    """POST /api/v1/sessions/from-url accepts optional survey metadata (returns 400/500 when URL fails)."""
    r = client.post(
        "/api/v1/sessions/from-url",
        headers={**tenant_headers, "Content-Type": "application/json"},
        json={
            "dataset_url": "https://example.com/nonexistent.dta",
            "survey_country_code": "BJ",
            "survey_year": 2017,
            "survey_type": "DHS",
        },
    )
    # Expect 400 (download will fail) or 500, but not 422 (validation error)
    assert r.status_code in (400, 500)


def test_compute_indicator(client: TestClient, tenant_headers: dict, session_id: str) -> None:
    """POST /api/v1/indicators/compute returns estimate and metadata."""
    r = client.post(
        "/api/v1/indicators/compute",
        headers=tenant_headers,
        json={
            "session_id": session_id,
            "indicator_id": "modern_contraception_rate",
            "use_weights": True,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "result" in data
    res = data["result"]
    assert "value" in res
    assert "metadata" in res
    assert 0 <= res["value"] <= 1


def test_compute_indicator_unknown_session(client: TestClient, tenant_headers: dict) -> None:
    """POST /api/v1/indicators/compute returns 404 for unknown session."""
    r = client.post(
        "/api/v1/indicators/compute",
        headers=tenant_headers,
        json={
            "session_id": "nonexistent",
            "indicator_id": "modern_contraception_rate",
        },
    )
    assert r.status_code == 404


def test_compute_grouped(client: TestClient, tenant_headers: dict, session_id: str) -> None:
    """POST /api/v1/indicators/compute-grouped returns rows per group."""
    r = client.post(
        "/api/v1/indicators/compute-grouped",
        headers=tenant_headers,
        json={
            "session_id": session_id,
            "indicator_id": "modern_contraception_rate",
            "group_by_column": "v025",
            "use_weights": True,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["indicator_id"] == "modern_contraception_rate"
    assert data["group_by_column"] == "v025"
    assert "rows" in data
    assert len(data["rows"]) >= 1
    for row in data["rows"]:
        assert "group_value" in row
        assert "estimate" in row
        assert "population_n" in row


def test_compute_grouped_missing_column(
    client: TestClient, tenant_headers: dict, session_id: str
) -> None:
    """POST /api/v1/indicators/compute-grouped returns 400 when group column is missing."""
    r = client.post(
        "/api/v1/indicators/compute-grouped",
        headers=tenant_headers,
        json={
            "session_id": session_id,
            "indicator_id": "modern_contraception_rate",
            "group_by_column": "nonexistent_column",
            "use_weights": True,
        },
    )
    assert r.status_code == 400


def test_compute_grouped_404(client: TestClient, tenant_headers: dict) -> None:
    """POST /api/v1/indicators/compute-grouped returns 404 for unknown session."""
    r = client.post(
        "/api/v1/indicators/compute-grouped",
        headers=tenant_headers,
        json={
            "session_id": "nonexistent",
            "indicator_id": "modern_contraception_rate",
            "group_by_column": "v025",
        },
    )
    assert r.status_code == 404


def test_spatial_aggregate(client: TestClient, tenant_headers: dict, session_id: str) -> None:
    """POST /api/v1/spatial/aggregate returns GeoJSON with estimate per admin."""
    r = client.post(
        "/api/v1/spatial/aggregate",
        headers=tenant_headers,
        json={
            "session_id": session_id,
            "indicator_id": "modern_contraception_rate",
            "country_code": "ETH",
            "admin_level": 1,
            "microdata_admin_column": "admin1_code",
            "boundary_admin_column": "admin_id",
            "use_weights": True,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["indicator_id"] == "modern_contraception_rate"
    assert data["country_code"] == "ETH"
    assert data["admin_level"] == 1
    assert "geojson" in data
    gj = data["geojson"]
    assert gj.get("type") == "FeatureCollection"
    assert "features" in gj
    assert len(gj["features"]) >= 1


def test_spatial_aggregate_unknown_session(client: TestClient, tenant_headers: dict) -> None:
    """POST /api/v1/spatial/aggregate returns 404 for unknown session."""
    r = client.post(
        "/api/v1/spatial/aggregate",
        headers=tenant_headers,
        json={
            "session_id": "nonexistent",
            "indicator_id": "modern_contraception_rate",
            "country_code": "ETH",
            "admin_level": 1,
            "microdata_admin_column": "admin1_code",
        },
    )
    assert r.status_code == 404
