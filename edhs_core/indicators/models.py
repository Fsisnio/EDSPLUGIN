from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConfidenceInterval(BaseModel):
    """Represents a (1 - alpha) confidence interval for an estimate."""

    lower: float = Field(..., description="Lower bound of the confidence interval.")
    upper: float = Field(..., description="Upper bound of the confidence interval.")
    level: float = Field(
        0.95,
        description="Confidence level, typically 0.95 for 95% CI.",
    )


class IndicatorMetadata(BaseModel):
    """
    Descriptive metadata for an indicator.

    This is intentionally verbose to support cataloging, auditability,
    and integration with admin dashboards.
    """

    id: str = Field(..., description="Unique identifier for the indicator.")
    name: str = Field(..., description="Human-readable indicator name.")
    description: str = Field(..., description="Short description of the indicator.")
    version: str = Field("1.0.0", description="Semantic version of the indicator logic.")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when this indicator run was created.",
    )
    dhs_variables: List[str] = Field(
        default_factory=list,
        description="List of DHS/EDHS variable names used.",
    )
    population_filter_description: Optional[str] = Field(
        default=None,
        description="Human-readable description of population filters applied.",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes or caveats about the indicator computation.",
    )


class IndicatorResult(BaseModel):
    """
    Standardized response for a single indicator computation.

    `value` is intentionally flexible: many indicators are scalars,
    but some (e.g. age-specific fertility rates) may return series.
    """

    indicator_id: str = Field(..., description="Identifier of the computed indicator.")
    metadata: IndicatorMetadata = Field(..., description="Metadata about this run.")
    value: Any = Field(..., description="Estimated indicator value(s).")
    ci: Optional[ConfidenceInterval] = Field(
        default=None,
        description="Confidence interval for the primary estimate, if available.",
    )
    population_n: int = Field(
        ...,
        description="Unweighted count of observations in the analysis population.",
    )
    population_weighted_n: float = Field(
        ...,
        description="Weighted sum of observations in the analysis population.",
    )
    numerator_n: Optional[int] = Field(
        default=None,
        description="Unweighted numerator count, when applicable (e.g. cases).",
    )
    denominator_n: Optional[int] = Field(
        default=None,
        description="Unweighted denominator count, when applicable.",
    )
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form structure for indicator-specific diagnostics.",
    )
