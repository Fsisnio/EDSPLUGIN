from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from .base import BaseIndicator
from .registry import register_indicator


@register_indicator
class TotalFertilityRate(BaseIndicator):
    """
    Approximate Total Fertility Rate (TFR).

    This implementation uses a simplified age-specific fertility rate
    (ASFR) approach:
    - `v012` is age in years
    - `births_last_3_years` is a derived variable representing the
      number of live births in the last 3 years for each woman.

    The TFR is approximated as 5 * sum(ASFR across 5-year age groups),
    where ASFR is births per woman-year in the last 3 years.

    This is intentionally a simplification. For production DHS-like
    TFR, you would plug in the full birth history recode logic.
    """

    id = "total_fertility_rate"
    name = "Total Fertility Rate"
    description = "Approximate total fertility rate using simplified ASFRs."
    dhs_variables = ["v012", "births_last_3_years", "v005"]

    def __init__(
        self,
        age_var: str = "v012",
        births_var: str = "births_last_3_years",
        min_age: int = 15,
        max_age: int = 49,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.age_var = age_var
        self.births_var = births_var
        self.min_age = min_age
        self.max_age = max_age

    def filter_population(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.age_var not in df.columns:
            raise ValueError(f"Age variable '{self.age_var}' not found for TFR indicator.")
        return df[(df[self.age_var] >= self.min_age) & (df[self.age_var] <= self.max_age)]

    def population_filter_description(self) -> Optional[str]:
        return f"Women aged {self.min_age}–{self.max_age}"

    def _compute_core(
        self,
        df: pd.DataFrame,
        weights: Optional[pd.Series],
    ) -> Dict[str, Any]:
        if self.births_var not in df.columns:
            raise ValueError(
                f"Births variable '{self.births_var}' not found for TFR indicator.",
            )

        age = df[self.age_var]
        births = df[self.births_var].astype(float)

        if weights is None:
            weights = pd.Series(1.0, index=births.index)

        # Define 5-year age groups.
        bins = list(range(self.min_age, self.max_age + 6, 5))
        labels = [f"{a}-{a + 4}" for a in range(self.min_age, self.max_age + 1, 5)]
        age_group = pd.cut(age, bins=bins, right=True, labels=labels, include_lowest=True)

        df_grouped = pd.DataFrame(
            {
                "age_group": age_group,
                "births": births,
                "weight": weights,
            },
        ).dropna(subset=["age_group"])

        # Births in last 3 years; woman-years ~ 3 * num_women.
        grouped = df_grouped.groupby("age_group")
        births_w = grouped.apply(lambda g: float((g["births"] * g["weight"]).sum()))
        women_w = grouped.apply(lambda g: float(g["weight"].sum()))

        woman_years = 3.0 * women_w
        asfr = births_w / woman_years.replace(0.0, np.nan)

        # TFR approximation: 5 * sum(ASFR over age groups)
        tfr_estimate = float(5.0 * asfr.sum(skipna=True))

        # Variance estimation for TFR is non-trivial; here we omit CI
        # and include a note that design-based variance is a premium feature.
        return {
            "estimate": tfr_estimate,
            "ci": None,
            "numerator_n": int((births > 0).sum()),
            "denominator_n": int(len(df)),
            "notes": (
                "TFR estimated using simplified ASFRs; "
                "variance not survey-design corrected. "
                "Use premium variance module for official estimates."
            ),
            "extra": {
                "asfr_by_age_group": asfr.to_dict(),
                "births_weighted_by_age_group": births_w.to_dict(),
            },
        }
