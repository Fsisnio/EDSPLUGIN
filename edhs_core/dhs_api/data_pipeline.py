"""
Post-process DHS Program API /data JSON: year window on Data[] and stable deduplication.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _survey_year(row: Dict[str, Any]) -> Optional[int]:
    raw = row.get("SurveyYear")
    if raw is None or raw == "":
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def filter_data_rows_by_survey_year(
    rows: List[Dict[str, Any]],
    year_start: int,
    year_end: int,
) -> List[Dict[str, Any]]:
    """Keep rows whose SurveyYear is inside [year_start, year_end] (when present)."""
    out: List[Dict[str, Any]] = []
    for r in rows:
        y = _survey_year(r)
        if y is None:
            out.append(r)
            continue
        if year_start <= y <= year_end:
            out.append(r)
    return out


def _dedupe_key(row: Dict[str, Any]) -> tuple:
    return (
        str(row.get("IndicatorId") or row.get("Indicator") or ""),
        str(row.get("CountryId") or row.get("CountryCode") or row.get("CountryName") or ""),
        str(row.get("SurveyId") or ""),
        str(row.get("CharacteristicId") or row.get("BreakoutID") or row.get("BreakoutLabel") or ""),
    )


def dedupe_dhs_data_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Drop duplicate logical rows; when duplicates differ by year, keep the latest SurveyYear.
    """
    if not rows:
        return rows

    def sy(r: Dict[str, Any]) -> int:
        return _survey_year(r) or 0

    sorted_rows = sorted(rows, key=sy, reverse=True)
    seen: set[tuple] = set()
    kept: List[Dict[str, Any]] = []
    for r in sorted_rows:
        k = _dedupe_key(r)
        if k in seen:
            continue
        seen.add(k)
        kept.append(r)
    kept.sort(key=sy)
    return kept


def process_dhs_data_response(
    result: Dict[str, Any],
    year_start: int,
    year_end: int,
    *,
    dedupe: bool = True,
) -> Dict[str, Any]:
    """Return a shallow copy of result with processed Data array."""
    rows = list(result.get("Data") or [])
    rows = filter_data_rows_by_survey_year(rows, year_start, year_end)
    if dedupe:
        rows = dedupe_dhs_data_rows(rows)
    out = {**result, "Data": rows}
    return out
