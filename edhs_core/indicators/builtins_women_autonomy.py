from typing import Any, Dict, Optional

import pandas as pd

from .base import BaseIndicator
from .registry import register_indicator


@register_indicator
class WomenDecisionAutonomyIndex(BaseIndicator):
    """
    Women decision-making autonomy index.

    This implementation assumes three binary variables capturing whether
    the woman participates in decisions on:
    - health care
    - large household purchases
    - visits to family/relatives

    Each item is coded 1 if the woman participates (alone or jointly),
    0 otherwise. The index is the mean of these three items.

    Variable names are configurable to match country-specific recodes.
    """

    id = "women_decision_autonomy_index"
    name = "Women Decision Autonomy Index"
    description = "Index (0–1) of women’s participation in key household decisions."
    dhs_variables = ["autonomy_health", "autonomy_purchases", "autonomy_visits", "v005"]

    def __init__(
        self,
        autonomy_health_var: str = "autonomy_health",
        autonomy_purchases_var: str = "autonomy_purchases",
        autonomy_visits_var: str = "autonomy_visits",
        min_age: int = 15,
        max_age: int = 49,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.autonomy_health_var = autonomy_health_var
        self.autonomy_purchases_var = autonomy_purchases_var
        self.autonomy_visits_var = autonomy_visits_var
        self.min_age = min_age
        self.max_age = max_age

    def filter_population(self, df: pd.DataFrame) -> pd.DataFrame:
        if "v012" not in df.columns:
            raise ValueError("Age variable 'v012' not found for autonomy index.")
        return df[(df["v012"] >= self.min_age) & (df["v012"] <= self.max_age)]

    def population_filter_description(self) -> Optional[str]:
        return f"Women aged {self.min_age}–{self.max_age}"

    def _compute_core(
        self,
        df: pd.DataFrame,
        weights: Optional[pd.Series],
    ) -> Dict[str, Any]:
        for var in [
            self.autonomy_health_var,
            self.autonomy_purchases_var,
            self.autonomy_visits_var,
        ]:
            if var not in df.columns:
                raise ValueError(f"Required autonomy variable '{var}' not found.")

        items = df[
            [
                self.autonomy_health_var,
                self.autonomy_purchases_var,
                self.autonomy_visits_var,
            ]
        ].astype(float)

        index = items.mean(axis=1)

        if weights is None:
            weights = pd.Series(1.0, index=index.index)

        from .stats import normalize_weights, weighted_mean

        mean_index = weighted_mean(index, weights)

        # Approximate variance of weighted mean using normalized weights.
        w_norm = normalize_weights(weights)
        diff = index - mean_index
        var = float(((w_norm**2) * (diff**2)).sum() / (1.0 - (w_norm**2).sum()))

        from .stats import normal_approx_ci

        lower, upper = normal_approx_ci(mean_index, var, alpha=self.alpha)

        return {
            "estimate": float(mean_index),
            "ci": {"lower": lower, "upper": upper, "level": 1.0 - self.alpha},
            "numerator_n": None,
            "denominator_n": int(len(index)),
            "extra": {"variance": var},
        }
