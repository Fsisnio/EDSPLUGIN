"""
Resolve plugin indicator results from DHS Program API /data payloads (aggregated Data[]).

These are catalog/statistics rows — not household microdata — so values are looked up,
not recomputed with survey weights.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from ..utils.sessions import SessionData
from .models import ConfidenceInterval, IndicatorMetadata, IndicatorResult
from .registry import get_indicator_class

# Plugin id → DHS Program API IndicatorId strings (any match in fetch is used)
MICRODATA_TO_DHS_INDICATOR_IDS: Dict[str, List[str]] = {
    "total_fertility_rate": ["FE_FRTR_W_TFR", "FE_FRTR_W_A15"],
    "modern_contraception_rate": [
        "CN_ANMC_C_ANY",
        "CN_ANMC_W_ANY",
        "CN_ANMC_C_MOD",
        "FP_CUSE_W_MOD",
    ],
    "stunting_prevalence": ["CN_NUTS_C_HA2", "CN_NUTR_C_HA2"],
}

_CANON = {k.upper() for ids in MICRODATA_TO_DHS_INDICATOR_IDS.values() for k in ids}


def _indicator_column(df: pd.DataFrame) -> str:
    for c in ("IndicatorId", "Indicator", "indicator_id"):
        if c in df.columns:
            return c
    raise ValueError(
        "API catalog table has no IndicatorId/Indicator column. "
        f"Columns present: {list(df.columns)}"
    )


def _value_column(sub: pd.DataFrame) -> str:
    for c in ("Value", "value", "SurveyStatistic", "Statistic"):
        if c in sub.columns:
            return c
    raise ValueError(
        "API catalog table has no Value column. "
        f"Columns present: {list(sub.columns)}"
    )


def _filter_catalog_by_plugin_indicator(df: pd.DataFrame, plugin_indicator_id: str) -> pd.DataFrame:
    dhs_ids = MICRODATA_TO_DHS_INDICATOR_IDS.get(plugin_indicator_id)
    if not dhs_ids:
        raise ValueError(
            f"No DHS Program API IndicatorId mapping for plugin indicator `{plugin_indicator_id}`. "
            "Choose another indicator or extend MICRODATA_TO_DHS_INDICATOR_IDS."
        )
    icol = _indicator_column(df)
    want = {x.upper().strip() for x in dhs_ids}
    col = df[icol].astype(str).str.strip().str.upper()
    return df.loc[col.isin(want)]


def _pick_rows_for_session_year(sub: pd.DataFrame, session: SessionData) -> pd.DataFrame:
    if sub.empty:
        return sub
    if "SurveyYear" not in sub.columns or session.survey_year is None:
        return sub
    sy = pd.to_numeric(sub["SurveyYear"], errors="coerce")
    exact = sub.loc[sy == session.survey_year]
    if not exact.empty:
        return exact
    # latest available year for this indicator slice
    idx = sy.idxmax()
    if pd.notna(idx):
        return sub.loc[[idx]]
    return sub


def compute_indicator_from_api_catalog(session: SessionData, plugin_indicator_id: str) -> IndicatorResult:
    if getattr(session, "session_kind", "microdata") != "api_catalog":
        raise RuntimeError("compute_indicator_from_api_catalog requires an api_catalog session")

    sub = _filter_catalog_by_plugin_indicator(session.df, plugin_indicator_id)
    sub = _pick_rows_for_session_year(sub, session)
    if sub.empty:
        dhs_ids = MICRODATA_TO_DHS_INDICATOR_IDS.get(plugin_indicator_id, [])
        raise ValueError(
            f"Fetched catalog has no rows for indicator(s) {dhs_ids}. "
            "Re-fetch from the DHS Program API including those IndicatorIds."
        )

    row = sub.iloc[0]
    vcol = _value_column(sub)
    raw_val = row[vcol]
    val_f = float(pd.to_numeric(raw_val, errors="coerce"))
    if pd.isna(val_f):
        raise ValueError(f"Could not parse catalog Value: {raw_val!r}")

    icol = _indicator_column(sub)
    dhs_row_id = str(row.get(icol, ""))

    indicator_cls = get_indicator_class(plugin_indicator_id)
    indicator = indicator_cls()
    meta = IndicatorMetadata(
        id=indicator.id,
        name=indicator.name,
        description=(
            f"{indicator.description} "
            "(**Value** taken from DHS Program API catalog row; not recomputed from survey microdata.)"
        ),
        version=indicator.version,
        dhs_variables=list(getattr(indicator, "dhs_variables", []) or []),
        notes="Aggregated statistic from STATcompiler/API `Data[]`.",
    )

    # Optional CI columns in some API rows
    ci: Optional[ConfidenceInterval] = None
    lo = row.get("CILow") if hasattr(row, "get") else None
    hi = row.get("CIHigh") if hasattr(row, "get") else None
    try:
        if lo is not None and hi is not None and str(lo) != "" and str(hi) != "":
            lo_f = float(pd.to_numeric(lo, errors="coerce"))
            hi_f = float(pd.to_numeric(hi, errors="coerce"))
            if not (pd.isna(lo_f) or pd.isna(hi_f)):
                ci = ConfidenceInterval(lower=lo_f, upper=hi_f, level=0.95)
    except (TypeError, ValueError):
        pass

    return IndicatorResult(
        indicator_id=plugin_indicator_id,
        metadata=meta,
        value=val_f,
        ci=ci,
        population_n=int(len(sub)),
        population_weighted_n=float(len(sub)),
        extra={"source": "dhs_api_catalog", "dhs_indicator_id": dhs_row_id},
    )


def compute_grouped_from_api_catalog(
    session: SessionData,
    plugin_indicator_id: str,
    group_by_column: str,
) -> pd.DataFrame:
    """Return a DataFrame with group_by_column, estimate, ci_*, population_n columns."""
    if getattr(session, "session_kind", "microdata") != "api_catalog":
        raise RuntimeError("api_catalog session required")

    if group_by_column not in session.df.columns:
        raise ValueError(
            f"Grouping column `{group_by_column}` is not in the API catalog table. "
            f"Available: {list(session.df.columns)}. "
            "Re-fetch with an API breakdown that adds the dimension you need, or use survey microdata."
        )

    sub = _filter_catalog_by_plugin_indicator(session.df, plugin_indicator_id)
    if sub.empty:
        raise ValueError("No catalog rows for this indicator.")

    icol = _indicator_column(sub)
    vcol = _value_column(sub)
    rows_out: List[Dict[str, Any]] = []
    for gv, grp in sub.groupby(group_by_column, dropna=False):
        if grp.empty:
            continue
        g2 = _pick_rows_for_session_year(grp, session)
        if g2.empty:
            continue
        r0 = g2.iloc[0]
        est = float(pd.to_numeric(r0[vcol], errors="coerce"))
        if pd.isna(est):
            continue
        row_dict: Dict[str, Any] = {
            group_by_column: gv,
            "estimate": est,
            "ci_lower": None,
            "ci_upper": None,
            "population_n": int(len(g2)),
            "population_weighted_n": float(len(g2)),
            "numerator_n": None,
            "denominator_n": None,
        }
        lo = r0.get("CILow")
        hi = r0.get("CIHigh")
        try:
            if lo is not None and hi is not None and str(lo) != "" and str(hi) != "":
                row_dict["ci_lower"] = float(pd.to_numeric(lo, errors="coerce"))
                row_dict["ci_upper"] = float(pd.to_numeric(hi, errors="coerce"))
        except (TypeError, ValueError):
            pass
        rows_out.append(row_dict)

    if not rows_out:
        raise ValueError("Could not build grouped estimates from catalog rows.")

    return pd.DataFrame(rows_out)
