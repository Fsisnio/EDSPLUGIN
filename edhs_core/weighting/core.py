from typing import Optional

import pandas as pd


def compute_weight_column(
    df: pd.DataFrame,
    weight_var: str = "v005",
    target_column: str = "weight",
) -> pd.DataFrame:
    """
    Compute a normalized weight column following DHS convention.

    The DHS standard weight is v005 / 1_000_000. This function will:
    - Check for the presence of the specified weight variable
    - Create or overwrite `target_column` with normalized weights

    Parameters
    ----------
    df:
        Input DataFrame containing DHS survey data.
    weight_var:
        Name of the raw weight variable (default: v005).
    target_column:
        Name of the normalized weight column to create.
    """

    if weight_var not in df.columns:
        raise ValueError(f"Weight variable '{weight_var}' not found in DataFrame.")

    df = df.copy()
    df[target_column] = df[weight_var] / 1_000_000.0
    return df


def get_weight_series(
    df: pd.DataFrame,
    weight_var: str = "v005",
    normalized: bool = True,
    existing_normalized_column: Optional[str] = "weight",
) -> pd.Series:
    """
    Return a Pandas Series of weights for use in indicator calculations.

    If `normalized` is True and `existing_normalized_column` exists, it is
    used. Otherwise, weights are computed on the fly from `weight_var`.
    """

    if normalized and existing_normalized_column and existing_normalized_column in df.columns:
        return df[existing_normalized_column]

    if weight_var not in df.columns:
        raise ValueError(f"Weight variable '{weight_var}' not found in DataFrame.")

    if normalized:
        return df[weight_var] / 1_000_000.0
    return df[weight_var]
