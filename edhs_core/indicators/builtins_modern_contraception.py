from typing import Any, Dict, Optional

import pandas as pd

from .base import BaseIndicator
from .registry import register_indicator


@register_indicator
class ModernContraceptionRate(BaseIndicator):
    """
    Modern contraception rate among women 15–49.

    This implementation assumes:
    - `v012` is age in years
    - `v025` is place of residence (not used here but common covariate)
    - `modern_method` is a binary indicator (1 = using modern method)

    In production, you can adapt `modern_method` via recoding or by
    pointing to country-specific DHS recode variables.
    """

    id = "modern_contraception_rate"
    name = "Modern Contraception Rate"
    description = "Proportion of women 15–49 using a modern contraceptive method."
    dhs_variables = ["v012", "modern_method", "v005"]

    def __init__(
        self,
        modern_method_var: str = "modern_method",
        min_age: int = 15,
        max_age: int = 49,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.modern_method_var = modern_method_var
        self.min_age = min_age
        self.max_age = max_age

    def filter_population(self, df: pd.DataFrame) -> pd.DataFrame:
        if "v012" not in df.columns:
            raise ValueError("Age variable 'v012' not found for contraception indicator.")

        return df[(df["v012"] >= self.min_age) & (df["v012"] <= self.max_age)]

    def population_filter_description(self) -> Optional[str]:
        return f"Women aged {self.min_age}–{self.max_age}"

    def _compute_core(
        self,
        df: pd.DataFrame,
        weights: Optional[pd.Series],
    ) -> Dict[str, Any]:
        return self._binary_proportion_indicator(
            df=df,
            variable=self.modern_method_var,
            success_value=1,
            weights=weights,
        )
