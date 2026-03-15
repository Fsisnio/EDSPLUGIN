from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from ..indicators.models import IndicatorResult


class HealthCheckResponse(BaseModel):
    """Response model for basic health check."""

    status: str = Field(..., description="Health status of the service.")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the health check was performed.",
    )


class DatasetUploadResponse(BaseModel):
    """
    Response returned after a dataset is uploaded for processing.

    The `session_id` is used in subsequent requests to compute
    indicators or spatial aggregations based on the uploaded dataset.
    Optional survey metadata is used to pre-fill UI and label exports.
    """

    session_id: str = Field(..., description="Opaque identifier for the processing session.")
    tenant_id: str = Field(..., description="Tenant associated with this session.")
    filename: str = Field(..., description="Original uploaded file name.")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the session was created.",
    )
    survey_country_code: Optional[str] = Field(
        None,
        description="ISO country code for the survey (e.g. ETH for Ethiopia).",
    )
    survey_year: Optional[int] = Field(
        None,
        description="Survey year (e.g. 2016, 2019, 2024).",
    )
    survey_type: Optional[str] = Field(
        None,
        description="Survey type: DHS, MIS, AIS, etc.",
    )


class SessionFromUrlRequest(BaseModel):
    """
    Request to create a session by downloading a dataset from an external URL.

    The URL may point to a .dta or .sav file, or to a .zip archive
    containing one. Optional survey metadata is stored with the session.
    """

    dataset_url: str = Field(..., description="HTTP(S) URL to the dataset file or ZIP archive.")
    survey_country_code: Optional[str] = Field(
        None,
        description="ISO country code for the survey (e.g. ETH, BJ).",
    )
    survey_year: Optional[int] = Field(
        None,
        description="Survey year (e.g. 2016, 2019).",
    )
    survey_type: Optional[str] = Field(
        None,
        description="Survey type: DHS, MIS, AIS, etc.",
    )


class SessionInfoResponse(BaseModel):
    """
    Session metadata returned by GET /sessions/{session_id}.
    Does not include microdata.
    """

    session_id: str = Field(..., description="Session identifier.")
    tenant_id: str = Field(..., description="Tenant associated with this session.")
    filename: Optional[str] = Field(None, description="Uploaded file name, if any.")
    created_at: datetime = Field(..., description="When the session was created.")
    survey_country_code: Optional[str] = Field(None, description="Survey country code.")
    survey_year: Optional[int] = Field(None, description="Survey year.")
    survey_type: Optional[str] = Field(None, description="Survey type (DHS, MIS, AIS).")


class IndicatorComputeRequest(BaseModel):
    """
    Request model to compute a single indicator on a given session.
    """

    session_id: str = Field(..., description="Session identifier returned from upload.")
    indicator_id: str = Field(..., description="Identifier of the indicator to compute.")
    use_weights: bool = Field(
        True,
        description="Whether to apply DHS weights (v005 / 1_000_000).",
    )
    weight_var: str = Field(
        "v005",
        description="Raw DHS weight variable to use.",
    )
    extra_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional indicator-specific parameters.",
    )


class IndicatorInfo(BaseModel):
    """
    Lightweight descriptor of an available indicator.
    """

    id: str = Field(..., description="Unique indicator identifier.")
    name: str = Field(..., description="Human-readable name.")
    description: str = Field(..., description="Short description.")


class IndicatorListResponse(BaseModel):
    """List of available indicators."""

    indicators: list[IndicatorInfo] = Field(
        ...,
        description="Registered indicators that can be computed.",
    )


class IndicatorComputeResponse(BaseModel):
    """Response model wrapping a single `IndicatorResult`."""

    result: IndicatorResult = Field(..., description="Computed indicator result.")


class IndicatorComputeGroupedRequest(BaseModel):
    """Request to compute an indicator by subgroup (e.g. residence, region)."""

    session_id: str = Field(..., description="Session identifier.")
    indicator_id: str = Field(..., description="Indicator to compute.")
    group_by_column: str = Field(
        ...,
        description="Column name to group by (e.g. v025, admin1_code, v106).",
    )
    use_weights: bool = Field(True, description="Whether to apply DHS weights.")
    weight_var: str = Field("v005", description="Weight variable.")
    extra_params: dict[str, Any] = Field(default_factory=dict)


class IndicatorGroupRow(BaseModel):
    """One row of disaggregated indicator output."""

    group_value: Any = Field(..., description="Value of the grouping variable.")
    estimate: float = Field(..., description="Indicator estimate for this group.")
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    population_n: int = Field(..., description="Unweighted N in group.")
    population_weighted_n: float = Field(..., description="Weighted N in group.")
    numerator_n: Optional[int] = None
    denominator_n: Optional[int] = None


class IndicatorComputeGroupedResponse(BaseModel):
    """Response for disaggregated indicator computation."""

    indicator_id: str = Field(..., description="Indicator that was computed.")
    group_by_column: str = Field(..., description="Column used for grouping.")
    rows: list[IndicatorGroupRow] = Field(..., description="One row per group.")


class SpatialAggregationRequest(BaseModel):
    """
    Request to aggregate an indicator by admin level and return GeoJSON.
    """

    session_id: str = Field(..., description="Session identifier for input microdata.")
    indicator_id: str = Field(..., description="Indicator to compute for each admin unit.")
    country_code: str = Field(..., description="ISO country code used to resolve admin boundaries.")
    admin_level: int = Field(
        ...,
        description="Administrative level to aggregate by (e.g. 1, 2).",
    )
    microdata_admin_column: str = Field(
        ...,
        description="Column in the microdata containing admin identifiers.",
    )
    boundary_admin_column: str = Field(
        "admin_id",
        description="Column in the boundary dataset containing admin identifiers.",
    )
    use_weights: bool = Field(
        True,
        description="Whether to apply DHS weights (v005 / 1_000_000).",
    )
    weight_var: str = Field(
        "v005",
        description="Raw DHS weight variable to use.",
    )
    extra_indicator_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional indicator-specific parameters.",
    )


class SpatialAggregationResponse(BaseModel):
    """
    GeoJSON result for choropleth-ready spatial aggregation.
    """

    indicator_id: str = Field(..., description="Identifier of the aggregated indicator.")
    country_code: str = Field(..., description="ISO country code of the boundaries.")
    admin_level: int = Field(..., description="Administrative level of aggregation.")
    geojson: Dict[str, Any] = Field(
        ...,
        description="GeoJSON FeatureCollection with admin polygons and indicator values.",
    )
