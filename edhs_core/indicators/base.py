from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd

from ..utils.sessions import SessionData
from ..weighting.core import get_weight_series
from .models import ConfidenceInterval, IndicatorMetadata, IndicatorResult
from .stats import normal_approx_ci, weighted_proportion


class BaseIndicator(ABC):
    """
    Abstract base class for all indicators.

    Subclasses should implement:
    - `id` (class attribute)
    - `name` (class attribute)
    - `description` (class attribute)
    - `dhs_variables` (class attribute, list of variable names)
    - `_compute_core` method for the indicator-specific logic
    """

    id: str = "base"
    name: str = "Base Indicator"
    description: str = "Abstract base indicator; do not use directly."
    version: str = "1.0.0"
    dhs_variables: List[str] = []

    def __init__(
        self,
        use_weights: bool = True,
        weight_var: str = "v005",
        weight_column: str = "weight",
        alpha: float = 0.05,
    ) -> None:
        self.use_weights = use_weights
        self.weight_var = weight_var
        self.weight_column = weight_column
        self.alpha = alpha

    # ------------------------------------------------------------------
    # Population filtering
    # ------------------------------------------------------------------
    def filter_population(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply indicator-specific population filters.

        Subclasses may override this to implement, for example:
        - Women age 15–49
        - Children under 5
        - Ever-married women, etc.
        """

        return df

    # ------------------------------------------------------------------
    # Core computation API
    # ------------------------------------------------------------------
    def compute_from_session(self, session: SessionData) -> IndicatorResult:
        """
        Entry point to compute an indicator from a `SessionData` object.
        """

        df = session.df
        return self.compute(df=df)

    def compute(self, df: pd.DataFrame) -> IndicatorResult:
        """
        Compute the indicator from a DataFrame.

        This method:
        - Applies population filters
        - Retrieves weights (if enabled)
        - Delegates to `_compute_core` for indicator-specific logic
        - Wraps results with standardized metadata
        """

        population_df = self.filter_population(df)
        population_n = int(len(population_df))

        if population_n == 0:
            raise ValueError("Population filter produced an empty dataset.")

        weights_series = None
        population_weighted_n = float(population_n)

        if self.use_weights:
            weights_series = get_weight_series(
                population_df,
                weight_var=self.weight_var,
                normalized=True,
                existing_normalized_column=self.weight_column,
            )
            population_weighted_n = float(weights_series.sum())

        core_result = self._compute_core(
            df=population_df,
            weights=weights_series,
        )

        metadata = IndicatorMetadata(
            id=self.id,
            name=self.name,
            description=self.description,
            version=self.version,
            dhs_variables=self.dhs_variables,
            population_filter_description=self.population_filter_description(),
            notes=core_result.get("notes"),
        )

        ci_obj: Optional[ConfidenceInterval] = None
        ci = core_result.get("ci")
        if ci is not None:
            ci_obj = ConfidenceInterval(
                lower=float(ci["lower"]),
                upper=float(ci["upper"]),
                level=float(ci.get("level", 0.95)),
            )

        return IndicatorResult(
            indicator_id=self.id,
            metadata=metadata,
            value=core_result["estimate"],
            ci=ci_obj,
            population_n=population_n,
            population_weighted_n=population_weighted_n,
            numerator_n=core_result.get("numerator_n"),
            denominator_n=core_result.get("denominator_n"),
            extra=core_result.get("extra", {}),
        )

    def compute_grouped(self, df: pd.DataFrame, group_by: str) -> pd.DataFrame:
        """
        Compute the indicator for sub-populations defined by `group_by`.

        Returns a DataFrame with one row per group, containing:
        - group identifier
        - estimate and (if available) confidence interval bounds
        - population counts (weighted and unweighted)
        - numerator/denominator counts, when applicable
        """

        population_df = self.filter_population(df)
        if group_by not in population_df.columns:
            raise ValueError(f"Grouping variable '{group_by}' not found.")

        rows = []
        for group_value, g in population_df.groupby(group_by):
            population_n = int(len(g))
            if population_n == 0:
                continue

            weights_series = None
            population_weighted_n = float(population_n)

            if self.use_weights:
                weights_series = get_weight_series(
                    g,
                    weight_var=self.weight_var,
                    normalized=True,
                    existing_normalized_column=self.weight_column,
                )
                population_weighted_n = float(weights_series.sum())

            core_result = self._compute_core(df=g, weights=weights_series)
            ci = core_result.get("ci")

            rows.append(
                {
                    group_by: group_value,
                    "estimate": core_result["estimate"],
                    "ci_lower": ci["lower"] if ci is not None else None,
                    "ci_upper": ci["upper"] if ci is not None else None,
                    "ci_level": ci.get("level", 1.0 - self.alpha) if ci is not None else None,  # type: ignore[union-attr]
                    "population_n": population_n,
                    "population_weighted_n": population_weighted_n,
                    "numerator_n": core_result.get("numerator_n"),
                    "denominator_n": core_result.get("denominator_n"),
                },
            )

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Hooks for subclasses
    # ------------------------------------------------------------------
    def population_filter_description(self) -> Optional[str]:
        """Human-readable description of the population filter."""

        return None

    @abstractmethod
    def _compute_core(
        self,
        df: pd.DataFrame,
        weights: Optional[pd.Series],
    ) -> Dict[str, Any]:
        """
        Indicator-specific computation logic.

        Implementations must return a dictionary with at minimum:
        - `estimate` (float or serializable structure)

        Optionally:
        - `ci`: dict with `lower`, `upper`, and optional `level`
        - `numerator_n`
        - `denominator_n`
        - `notes`
        - `extra`
        """

    # ------------------------------------------------------------------
    # Helper methods for common patterns
    # ------------------------------------------------------------------
    def _binary_proportion_indicator(
        self,
        df: pd.DataFrame,
        variable: str,
        success_value: Any = 1,
        weights: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        """
        Convenience helper for binary (0/1) or categorical proportion indicators.
        """

        if variable not in df.columns:
            raise ValueError(f"Required variable '{variable}' not found.")

        series = df[variable]
        indicator = (series == success_value).astype(int)

        if weights is None:
            weights = pd.Series(1.0, index=indicator.index)

        p_hat, var = weighted_proportion(indicator, weights)
        lower, upper = normal_approx_ci(p_hat, var, alpha=self.alpha)

        return {
            "estimate": float(p_hat),
            "ci": {"lower": lower, "upper": upper, "level": 1.0 - self.alpha},
            "numerator_n": int(indicator.sum()),
            "denominator_n": int(len(indicator)),
            "extra": {"variance": var},
        }
