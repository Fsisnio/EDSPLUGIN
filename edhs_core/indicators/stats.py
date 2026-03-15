from math import sqrt
from statistics import NormalDist
from typing import Tuple

import pandas as pd


def normalize_weights(weights: pd.Series) -> pd.Series:
    """
    Return weights normalized to sum to 1.

    This is intentionally public so that indicator implementations
    can reuse a consistent normalization strategy.
    """

    w = weights.astype(float)
    total = w.sum()
    if total <= 0:
        raise ValueError("Sum of weights must be positive.")
    return w / total


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    """Compute a weighted mean."""

    w = weights.astype(float)
    v = values.astype(float)
    denom = w.sum()
    if denom <= 0:
        raise ValueError("Sum of weights must be positive.")
    return float((w * v).sum() / denom)


def weighted_proportion(
    indicator: pd.Series,
    weights: pd.Series,
) -> Tuple[float, float]:
    """
    Compute a weighted proportion and its approximate variance.

    The indicator series is expected to be binary (0/1). Variance is
    calculated using a standard normalized-weights approximation.
    """

    v = indicator.astype(float)
    w_norm = normalize_weights(weights)
    p_hat = float((w_norm * v).sum())

    # Approximate variance under normalized weights
    diff = v - p_hat
    var = float(((w_norm**2) * (diff**2)).sum() / (1.0 - (w_norm**2).sum()))
    return p_hat, var


def normal_approx_ci(
    estimate: float,
    variance: float,
    alpha: float = 0.05,
) -> Tuple[float, float]:
    """
    Compute a normal-approximation confidence interval.

    This is intentionally generic and used as a building block for
    proportion/mean CIs. For survey-design-corrected variance, a
    premium module can plug in alternative variance estimators.
    """

    if variance < 0:
        raise ValueError("Variance must be non-negative.")

    if alpha <= 0 or alpha >= 1:
        raise ValueError("Alpha must be between 0 and 1.")

    # Use Python's standard NormalDist to avoid extra dependencies.
    z = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    margin = z * sqrt(variance)
    return estimate - margin, estimate + margin
