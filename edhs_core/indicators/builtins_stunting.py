from typing import Any, Dict, Optional

import pandas as pd

from .base import BaseIndicator
from .registry import register_indicator


@register_indicator
class StuntingPrevalence(BaseIndicator):
    """
    Stunting prevalence among children under five.

    This implementation assumes:
    - `hc70` is the height-for-age z-score (HAZ) * 100
    - Children under five are identified via `age_months` variable
      (age in months); this can be adapted to specific DHS recodes.
    - Stunting is defined as HAZ < -2 SD.
    """

    id = "stunting_prevalence"
    name = "Stunting Prevalence"
    description = "Prevalence of stunting (HAZ < -2 SD) among children under five."
    # Support both KR/PR-style `hc70` and BR-style `hw70`, and age from `b19` (age in months).
    dhs_variables = ["hc70", "hw70", "b19", "v005"]

    def __init__(
        self,
        haz_var: str = "hc70",
        age_months_var: str = "b19",
        max_age_months: int = 59,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.haz_var = haz_var
        self.age_months_var = age_months_var
        self.max_age_months = max_age_months

    def filter_population(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.age_months_var not in df.columns:
            raise ValueError(
                f"Age variable '{self.age_months_var}' not found for stunting indicator.",
            )
        return df[df[self.age_months_var] <= self.max_age_months]

    def population_filter_description(self) -> Optional[str]:
        return f"Children under {self.max_age_months + 1} months"

    def _compute_core(
        self,
        df: pd.DataFrame,
        weights: Optional[pd.Series],
    ) -> Dict[str, Any]:
        haz_var = self.haz_var
        if haz_var not in df.columns:
            # Fallback for BR-style files that use `hw70` instead of `hc70`.
            if "hw70" in df.columns:
                haz_var = "hw70"
            else:
                raise ValueError(f"HAZ variable '{self.haz_var}' (or 'hw70') not found.")

        # Convert HAZ * 100 back to HAZ.
        haz = df[haz_var] / 100.0
        stunted = (haz < -2.0).astype(int)

        if weights is None:
            weights = pd.Series(1.0, index=stunted.index)

        from .stats import normal_approx_ci, weighted_proportion

        p_hat, var = weighted_proportion(stunted, weights)
        lower, upper = normal_approx_ci(p_hat, var, alpha=self.alpha)

        return {
            "estimate": float(p_hat),
            "ci": {"lower": lower, "upper": upper, "level": 1.0 - self.alpha},
            "numerator_n": int(stunted.sum()),
            "denominator_n": int(len(stunted)),
            "extra": {"variance": var},
        }
