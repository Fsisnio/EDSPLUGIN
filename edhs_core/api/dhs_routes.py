"""
DHS Program API proxy routes.

Exposes indicators, countries, surveys, and data from api.dhsprogram.com
with optional CSV/JSON export.
"""

import csv
import io
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from ..config import settings
from ..dhs_api.client import DhsProgramApiClient

logger = logging.getLogger("edhs_core.dhs_api")

router = APIRouter(prefix="/dhs-api", tags=["DHS Program API"])


def _get_client() -> DhsProgramApiClient:
    """Get DHS Program API client; raise if API key not configured."""
    key = settings.DHS_PROGRAM_API_KEY
    if not key or not key.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DHS Program API key not configured. Set DHS_PROGRAM_API_KEY in environment.",
        )
    return DhsProgramApiClient(api_key=key.strip())


@router.get("/indicators")
async def dhs_list_indicators(
    country_ids: Optional[str] = Query(None, description="Comma-separated country codes (e.g. ET,BJ)"),
    indicator_ids: Optional[str] = Query(None, description="Comma-separated indicator IDs"),
    page: Optional[int] = Query(None),
    per_page: Optional[int] = Query(None, alias="perpage"),
) -> Dict[str, Any]:
    """
    List indicators from the DHS Program API (STATcompiler catalog).
    """
    try:
        client = _get_client()
        return client.get_indicators(
            country_ids=country_ids,
            indicator_ids=indicator_ids,
            page=page,
            per_page=per_page,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("DHS API indicators request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DHS Program API request failed: {e}",
        ) from e


@router.get("/countries")
async def dhs_list_countries(
    country_ids: Optional[str] = Query(None),
    survey_ids: Optional[str] = Query(None),
    survey_year: Optional[int] = Query(None),
    survey_year_start: Optional[int] = Query(None),
    survey_year_end: Optional[int] = Query(None),
    page: Optional[int] = Query(None),
    per_page: Optional[int] = Query(None, alias="perpage"),
) -> Dict[str, Any]:
    """
    List countries with DHS surveys from the DHS Program API.
    """
    try:
        client = _get_client()
        return client.get_countries(
            country_ids=country_ids,
            survey_ids=survey_ids,
            survey_year=survey_year,
            survey_year_start=survey_year_start,
            survey_year_end=survey_year_end,
            page=page,
            per_page=per_page,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("DHS API countries request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DHS Program API request failed: {e}",
        ) from e


@router.get("/surveys")
async def dhs_list_surveys(
    country_ids: Optional[str] = Query(None),
    survey_ids: Optional[str] = Query(None),
    survey_year: Optional[int] = Query(None),
    survey_year_start: Optional[int] = Query(None),
    survey_year_end: Optional[int] = Query(None),
    survey_type: Optional[str] = Query(None),
    indicator_ids: Optional[str] = Query(None),
    page: Optional[int] = Query(None),
    per_page: Optional[int] = Query(None, alias="perpage"),
) -> Dict[str, Any]:
    """
    List surveys from the DHS Program API.
    """
    try:
        client = _get_client()
        return client.get_surveys(
            country_ids=country_ids,
            survey_ids=survey_ids,
            survey_year=survey_year,
            survey_year_start=survey_year_start,
            survey_year_end=survey_year_end,
            survey_type=survey_type,
            indicator_ids=indicator_ids,
            page=page,
            per_page=per_page,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("DHS API surveys request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DHS Program API request failed: {e}",
        ) from e


@router.get("/data")
async def dhs_get_data(
    country_ids: str = Query(..., description="Comma-separated country codes (e.g. ET,BJ)"),
    indicator_ids: str = Query(..., description="Comma-separated indicator IDs"),
    survey_ids: Optional[str] = Query(None),
    survey_year: Optional[int] = Query(None),
    survey_year_start: Optional[int] = Query(None),
    survey_year_end: Optional[int] = Query(None),
    characteristic_ids: Optional[str] = Query(None),
    breakdown: Optional[str] = Query(None),
    return_geometry: Optional[bool] = Query(None),
    page: Optional[int] = Query(None),
    per_page: Optional[int] = Query(None, alias="perpage"),
) -> Dict[str, Any]:
    """
    Fetch indicator data from the DHS Program API (STATcompiler aggregated data).
    """
    try:
        client = _get_client()
        return client.get_data(
            country_ids=country_ids,
            indicator_ids=indicator_ids,
            survey_ids=survey_ids,
            survey_year=survey_year,
            survey_year_start=survey_year_start,
            survey_year_end=survey_year_end,
            characteristic_ids=characteristic_ids,
            breakdown=breakdown,
            return_geometry=return_geometry,
            page=page,
            per_page=per_page,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("DHS API data request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DHS Program API request failed: {e}",
        ) from e


@router.get("/data/export/csv")
async def dhs_export_data_csv(
    country_ids: str = Query(..., description="Comma-separated country codes"),
    indicator_ids: str = Query(..., description="Comma-separated indicator IDs"),
    survey_ids: Optional[str] = Query(None),
    survey_year: Optional[int] = Query(None),
    survey_year_start: Optional[int] = Query(None),
    survey_year_end: Optional[int] = Query(None),
) -> StreamingResponse:
    """
    Export DHS Program API indicator data as CSV.
    """
    try:
        client = _get_client()
        result = client.get_data(
            country_ids=country_ids,
            indicator_ids=indicator_ids,
            survey_ids=survey_ids,
            survey_year=survey_year,
            survey_year_start=survey_year_start,
            survey_year_end=survey_year_end,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("DHS API data export failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DHS Program API request failed: {e}",
        ) from e

    data = result.get("Data", [])
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No data returned for the given filters.",
        )

    # Build CSV from first row keys
    fieldnames = list(data[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=dhs_program_data_export.csv",
        },
    )


@router.get("/data/export/json")
async def dhs_export_data_json(
    country_ids: str = Query(..., description="Comma-separated country codes"),
    indicator_ids: str = Query(..., description="Comma-separated indicator IDs"),
    survey_ids: Optional[str] = Query(None),
    survey_year: Optional[int] = Query(None),
    survey_year_start: Optional[int] = Query(None),
    survey_year_end: Optional[int] = Query(None),
) -> StreamingResponse:
    """
    Export DHS Program API indicator data as JSON.
    """
    try:
        client = _get_client()
        result = client.get_data(
            country_ids=country_ids,
            indicator_ids=indicator_ids,
            survey_ids=survey_ids,
            survey_year=survey_year,
            survey_year_start=survey_year_start,
            survey_year_end=survey_year_end,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("DHS API data export failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DHS Program API request failed: {e}",
        ) from e

    data = result.get("Data", [])
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No data returned for the given filters.",
        )

    return StreamingResponse(
        iter([json.dumps(result, indent=2)]),
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=dhs_program_data_export.json",
        },
    )
