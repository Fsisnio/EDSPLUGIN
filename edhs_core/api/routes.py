import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import pyreadstat
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from ..indicators import BaseIndicator
from ..indicators.dhs_api_catalog import (
    compute_grouped_from_api_catalog,
    compute_indicator_from_api_catalog,
)
from ..indicators.registry import get_indicator_class
from ..security.dependencies import get_current_tenant, require_active_subscription
from ..spatial.aggregation import (
    aggregate_indicator_by_admin,
    geodf_to_choropleth_geojson,
    load_admin_boundaries,
)
from ..utils.sessions import SessionManager, get_session_manager
from .schemas import (
    DatasetUploadResponse,
    DhsApiCatalogSessionRequest,
    HealthCheckResponse,
    IndicatorComputeGroupedRequest,
    IndicatorComputeGroupedResponse,
    IndicatorComputeRequest,
    IndicatorComputeResponse,
    IndicatorInfo,
    IndicatorListResponse,
    SessionFromUrlRequest,
    SessionInfoResponse,
    SpatialAggregationRequest,
    SpatialAggregationResponse,
)

api_router = APIRouter()


@api_router.get("", include_in_schema=False)
async def api_root() -> dict:
    """
    Root of the API v1. Returns service info and links so that
    visiting /api/v1 in a browser gives a valid response.
    """
    return {
        "service": "DHS Hybrid Plugin Platform API",
        "version": "v1",
        "docs": "/docs",
        "health": "/api/v1/health",
        "indicators": "/api/v1/indicators",
        "sessions_upload": "POST /api/v1/sessions/upload",
        "sessions_from_url": "POST /api/v1/sessions/from-url",
        "sessions_from_dhs_api_catalog": "POST /api/v1/sessions/from-dhs-api-catalog",
        "indicators_compute": "POST /api/v1/indicators/compute",
        "indicators_compute_grouped": "POST /api/v1/indicators/compute-grouped",
        "spatial_aggregate": "POST /api/v1/spatial/aggregate",
        "dhs_api_indicators": "GET /api/v1/dhs-api/indicators",
        "dhs_api_countries": "GET /api/v1/dhs-api/countries",
        "dhs_api_data": "GET /api/v1/dhs-api/data",
        "dhs_api_export_csv": "GET /api/v1/dhs-api/data/export/csv",
        "dhs_api_export_json": "GET /api/v1/dhs-api/data/export/json",
    }


@api_router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """
    Lightweight health check endpoint.

    Does not touch any sensitive data; can be used by monitoring
    systems and load balancers.
    """

    return HealthCheckResponse(status="ok")


@api_router.post(
    "/sessions/upload",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_active_subscription)],
)
async def upload_dataset(
    file: UploadFile = File(...),
    survey_country_code: Optional[str] = Form(None),
    survey_year: Optional[str] = Form(None),
    survey_type: Optional[str] = Form(None),
    tenant_id: str = Depends(get_current_tenant),
    session_manager: SessionManager = Depends(get_session_manager),
) -> DatasetUploadResponse:
    """
    Upload a DHS/EDHS dataset for session-based processing.

    Optional form fields: survey_country_code (e.g. ETH), survey_year (e.g. 2019),
    survey_type (e.g. DHS, MIS, AIS). These are stored with the session for
    UI pre-fill and exports.
    """

    year_int: Optional[int] = None
    if survey_year and survey_year.strip():
        try:
            year_int = int(survey_year.strip())
        except ValueError:
            pass

    try:
        session_id = await session_manager.create_session_from_upload(
            tenant_id=tenant_id,
            upload=file,
            survey_country_code=(survey_country_code or "").strip() or None,
            survey_year=year_int,
            survey_type=(survey_type or "").strip() or None,
        )
        session = session_manager.get_session(tenant_id=tenant_id, session_id=session_id)
        return DatasetUploadResponse(
            session_id=session_id,
            tenant_id=tenant_id,
            filename=file.filename or "",
            survey_country_code=session.survey_country_code,
            survey_year=session.survey_year,
            survey_type=session.survey_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger("edhs_core").exception("Upload failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed. The file may be corrupt or in an unsupported format.",
        ) from e


@api_router.post(
    "/sessions/from-url",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_active_subscription)],
)
async def create_session_from_url(
    payload: SessionFromUrlRequest,
    tenant_id: str = Depends(get_current_tenant),
    session_manager: SessionManager = Depends(get_session_manager),
) -> DatasetUploadResponse:
    """
    Create a session by downloading a DHS/EDHS dataset from an external URL.

    The URL may point to a .dta or .sav file, or to a .zip archive containing
    one. Optional survey metadata is stored with the session for UI and exports.
    """
    try:
        session_id = await session_manager.create_session_from_url(
            tenant_id=tenant_id,
            dataset_url=payload.dataset_url.strip(),
            survey_country_code=payload.survey_country_code,
            survey_year=payload.survey_year,
            survey_type=payload.survey_type,
        )
        session = session_manager.get_session(tenant_id=tenant_id, session_id=session_id)
        return DatasetUploadResponse(
            session_id=session_id,
            tenant_id=tenant_id,
            filename=session.filename or "from_url",
            survey_country_code=session.survey_country_code,
            survey_year=session.survey_year,
            survey_type=session.survey_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger("edhs_core").exception("Create session from URL failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session from URL. The URL may be invalid or the file unsupported.",
        ) from e


@api_router.post(
    "/sessions/from-dhs-api-catalog",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_active_subscription)],
)
async def create_session_from_dhs_api_catalog(
    payload: DhsApiCatalogSessionRequest,
    tenant_id: str = Depends(get_current_tenant),
    session_manager: SessionManager = Depends(get_session_manager),
) -> DatasetUploadResponse:
    """
    Create a session whose table is the DHS Program API ``Data`` array (aggregated statistics).

    Use the same ``/indicators/compute`` endpoint; values are read from catalog rows when
    ``session_kind`` is ``api_catalog``, not recomputed from survey microdata.
    """
    session_id = await session_manager.create_session_from_dhs_api_catalog(
        tenant_id=tenant_id,
        dhs_data=payload.dhs_data,
        survey_country_code=payload.survey_country_code,
        survey_year=payload.survey_year,
        survey_type=payload.survey_type,
    )
    session = session_manager.get_session(tenant_id=tenant_id, session_id=session_id)
    return DatasetUploadResponse(
        session_id=session_id,
        tenant_id=tenant_id,
        filename=session.filename or "dhs_program_api_catalog.json",
        survey_country_code=session.survey_country_code,
        survey_year=session.survey_year,
        survey_type=session.survey_type,
    )


@api_router.post(
    "/test/mock-session",
    response_model=DatasetUploadResponse,
)
async def create_mock_session(
    survey_country_code: Optional[str] = None,
    survey_year: Optional[str] = None,
    survey_type: Optional[str] = None,
    tenant_id: str = Depends(get_current_tenant),
    session_manager: SessionManager = Depends(get_session_manager),
) -> DatasetUploadResponse:
    """
    Create a synthetic in-memory session for testing.

    Optional query params apply only to the **synthetic** fallback (no BJBR71 file).
    If `data/BJBR71FL.DTA` is present, the session is always Benin (BJ) 2017 DHS microdata
    so labels match the rows (sidebar/API country hints are ignored for that branch).
    """
    year_int: Optional[int] = None
    if survey_year and survey_year.strip():
        try:
            year_int = int(survey_year.strip())
        except ValueError:
            pass

    # Prefer using a real DHS file from Benin (BJBR71FL.DTA) as sample data if present locally.
    # This stays process-local and is only used to populate an in-memory session.
    benin_path = Path("data/BJBR71FL.DTA")
    if benin_path.exists():
        try:
            df, _ = pyreadstat.read_dta(
                benin_path,
                apply_value_formats=False,
                formats_as_category=False,
            )
            # Recode v313 (current method) to modern_method for builtin indicators.
            # DHS v313: 0=no method, 1-9=modern methods (pill, IUD, injectables, etc.)
            df = df.copy()
            if "v313" in df.columns and "modern_method" not in df.columns:
                df["modern_method"] = ((df["v313"] >= 1) & (df["v313"] <= 9)).astype(int)
            # Add admin1_code from v024 for spatial aggregation (matches ADM1_1, ADM1_2, ...)
            if "v024" in df.columns and "admin1_code" not in df.columns:
                df["admin1_code"] = "ADM1_" + df["v024"].astype(str)
            # Metadata must match the file (Benin DHS7); do not relabel as sidebar/API country.
            session_id = await session_manager.create_session_from_dataframe(
                tenant_id=tenant_id,
                df=df,
                filename=benin_path.name,
                survey_country_code="BJ",
                survey_year=2017,
                survey_type="DHS",
            )
            session = session_manager.get_session(tenant_id=tenant_id, session_id=session_id)
            return DatasetUploadResponse(
                session_id=session_id,
                tenant_id=tenant_id,
                filename=benin_path.name,
                survey_country_code=session.survey_country_code,
                survey_year=session.survey_year,
                survey_type=session.survey_type,
            )
        except Exception:
            # Fall back to synthetic data below if reading Benin file fails for any reason.
            logging.getLogger("edhs_core").warning(
                "Failed to use BJBR71FL.DTA as sample data; falling back to synthetic mock session.",
            )

    # Synthetic tiny dataset fallback (used only if real Benin data is not available).
    data = {
        "v001": [1, 1, 2, 2, 3, 3],
        "admin1_code": ["ADM1_1", "ADM1_1", "ADM1_1", "ADM1_2", "ADM1_2", "ADM1_3"],
        "v005": [1_000_000, 1_000_000, 1_000_000, 1_000_000, 1_000_000, 1_000_000],
        "v012": [20, 30, 25, 40, 17, 38],
        "v025": [1, 1, 2, 2, 1, 2],  # 1=urban, 2=rural (residence)
        "v106": [2, 1, 3, 1, 2, 2],  # education level
        "v190": [2, 1, 3, 2, 4, 1],  # wealth quintile
        "modern_method": [1, 0, 1, 1, 0, 0],
        "age_months": [10, 20, 30, 40, 50, 70],
        "hc70": [-250, -150, -300, -100, -180, -150],
        "births_last_3_years": [0, 1, 0, 2, 0, 1],
        "autonomy_health": [1, 1, 0, 1, 0, 0],
        "autonomy_purchases": [1, 0, 0, 1, 0, 0],
        "autonomy_visits": [1, 1, 1, 0, 0, 0],
    }
    df = pd.DataFrame(data)

    session_id = await session_manager.create_session_from_dataframe(
        tenant_id=tenant_id,
        df=df,
        filename="synthetic_mock",
        survey_country_code=survey_country_code,
        survey_year=year_int,
        survey_type=survey_type or "DHS",
    )
    session = session_manager.get_session(tenant_id=tenant_id, session_id=session_id)
    return DatasetUploadResponse(
        session_id=session_id,
        tenant_id=tenant_id,
        filename="synthetic_mock",
        survey_country_code=session.survey_country_code,
        survey_year=session.survey_year,
        survey_type=session.survey_type,
    )


@api_router.get(
    "/sessions/{session_id}",
    response_model=SessionInfoResponse,
    dependencies=[Depends(require_active_subscription)],
)
async def get_session_info(
    session_id: str,
    tenant_id: str = Depends(get_current_tenant),
    session_manager: SessionManager = Depends(get_session_manager),
) -> SessionInfoResponse:
    """
    Return metadata for an existing session (no microdata).
    Used to pre-fill survey country/year/type in the UI.
    """
    session = session_manager.get_session(tenant_id=tenant_id, session_id=session_id)
    return SessionInfoResponse(
        session_id=session_id,
        tenant_id=session.tenant_id,
        filename=session.filename,
        created_at=session.created_at,
        survey_country_code=session.survey_country_code,
        survey_year=session.survey_year,
        survey_type=session.survey_type,
        session_kind=getattr(session, "session_kind", "microdata"),
    )


@api_router.get(
    "/indicators",
    response_model=IndicatorListResponse,
    dependencies=[Depends(require_active_subscription)],
)
async def list_available_indicators() -> IndicatorListResponse:
    """
    List all registered indicators.

    This is used by clients (QGIS plugin, web dashboard) to populate
    indicator selection UIs.
    """

    infos: list[IndicatorInfo] = []
    from ..indicators.registry import get_indicator_registry

    registry = get_indicator_registry()
    for indicator_id, cls in registry.items():
        # Instantiate temporarily to read static metadata.
        indicator: BaseIndicator = cls()
        infos.append(
            IndicatorInfo(
                id=indicator_id,
                name=indicator.name,
                description=indicator.description,
            ),
        )
    return IndicatorListResponse(indicators=infos)


@api_router.post(
    "/indicators/compute",
    response_model=IndicatorComputeResponse,
    dependencies=[Depends(require_active_subscription)],
)
async def compute_indicator(
    payload: IndicatorComputeRequest,
    tenant_id: str = Depends(get_current_tenant),
    session_manager: SessionManager = Depends(get_session_manager),
) -> IndicatorComputeResponse:
    """
    Compute a single indicator for a given session.

    This endpoint:
    - Retrieves the in-memory session (no microdata persistence)
    - Resolves the indicator class from the registry
    - Instantiates the indicator with requested weighting behavior
      and any extra parameters
    - Returns a standardized `IndicatorResult`
    """

    session = session_manager.get_session(tenant_id=tenant_id, session_id=payload.session_id)

    if getattr(session, "session_kind", "microdata") == "api_catalog":
        try:
            result = compute_indicator_from_api_catalog(session, payload.indicator_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return IndicatorComputeResponse(result=result)

    indicator_cls = get_indicator_class(payload.indicator_id)
    indicator: BaseIndicator = indicator_cls(
        use_weights=payload.use_weights,
        weight_var=payload.weight_var,
        **payload.extra_params,
    )
    try:
        result = indicator.compute_from_session(session)
    except ValueError as e:
        # Surface indicator-specific validation issues (e.g. missing columns) as 400s.
        raise HTTPException(status_code=400, detail=str(e)) from e
    return IndicatorComputeResponse(result=result)


@api_router.post(
    "/indicators/compute-grouped",
    response_model=IndicatorComputeGroupedResponse,
    dependencies=[Depends(require_active_subscription)],
)
async def compute_indicator_grouped(
    payload: IndicatorComputeGroupedRequest,
    tenant_id: str = Depends(get_current_tenant),
    session_manager: SessionManager = Depends(get_session_manager),
) -> IndicatorComputeGroupedResponse:
    """
    Compute an indicator disaggregated by a grouping variable (e.g. residence, region).
    Returns one estimate per group with optional CI and counts.
    """
    from .schemas import IndicatorGroupRow

    session = session_manager.get_session(tenant_id=tenant_id, session_id=payload.session_id)

    if getattr(session, "session_kind", "microdata") == "api_catalog":
        try:
            df = compute_grouped_from_api_catalog(
                session,
                payload.indicator_id,
                payload.group_by_column,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    else:
        indicator_cls = get_indicator_class(payload.indicator_id)
        indicator: BaseIndicator = indicator_cls(
            use_weights=payload.use_weights,
            weight_var=payload.weight_var,
            **payload.extra_params,
        )
        try:
            df = indicator.compute_grouped(session.df, group_by=payload.group_by_column)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    group_col = payload.group_by_column
    rows = []
    for _, r in df.iterrows():
        group_val = r[group_col]
        if pd.isna(group_val):
            group_val = None
        rows.append(
            IndicatorGroupRow(
                group_value=group_val,
                estimate=float(r["estimate"]),
                ci_lower=float(r["ci_lower"])
                if r.get("ci_lower") is not None and not pd.isna(r["ci_lower"])
                else None,
                ci_upper=float(r["ci_upper"])
                if r.get("ci_upper") is not None and not pd.isna(r["ci_upper"])
                else None,
                population_n=int(r["population_n"]),
                population_weighted_n=float(r["population_weighted_n"]),
                numerator_n=int(r["numerator_n"])
                if r.get("numerator_n") is not None and not pd.isna(r["numerator_n"])
                else None,
                denominator_n=int(r["denominator_n"])
                if r.get("denominator_n") is not None and not pd.isna(r["denominator_n"])
                else None,
            )
        )
    return IndicatorComputeGroupedResponse(
        indicator_id=payload.indicator_id,
        group_by_column=payload.group_by_column,
        rows=rows,
    )


@api_router.post(
    "/spatial/aggregate",
    response_model=SpatialAggregationResponse,
    dependencies=[Depends(require_active_subscription)],
)
async def spatial_aggregate_indicator(
    payload: SpatialAggregationRequest,
    tenant_id: str = Depends(get_current_tenant),
    session_manager: SessionManager = Depends(get_session_manager),
) -> SpatialAggregationResponse:
    """
    Aggregate an indicator by admin level and return choropleth-ready GeoJSON.
    """
    try:
        session = session_manager.get_session(tenant_id=tenant_id, session_id=payload.session_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Session not found or expired.") from e

    if getattr(session, "session_kind", "microdata") == "api_catalog":
        raise HTTPException(
            status_code=400,
            detail="Choropleth / spatial aggregation requires survey microdata with admin codes, "
            "not DHS Program API catalog rows.",
        )

    try:
        indicator_cls = get_indicator_class(payload.indicator_id)
    except KeyError as e:
        raise HTTPException(
            status_code=404, detail=f"Unknown indicator: {payload.indicator_id}"
        ) from e

    indicator: BaseIndicator = indicator_cls(
        use_weights=payload.use_weights,
        weight_var=payload.weight_var,
        **payload.extra_indicator_params,
    )

    try:
        admin_gdf = load_admin_boundaries(
            country_code=payload.country_code,
            admin_level=payload.admin_level,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        merged = aggregate_indicator_by_admin(
            session=session,
            indicator=indicator,
            group_by_column=payload.microdata_admin_column,
            admin_gdf=admin_gdf,
            admin_id_column=payload.boundary_admin_column,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        geojson = geodf_to_choropleth_geojson(
            merged,
            value_column="estimate",
            id_column=payload.boundary_admin_column,
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=500, detail=f"GeoJSON conversion failed: {e}") from e

    return SpatialAggregationResponse(
        indicator_id=payload.indicator_id,
        country_code=payload.country_code,
        admin_level=payload.admin_level,
        geojson=geojson,
    )
