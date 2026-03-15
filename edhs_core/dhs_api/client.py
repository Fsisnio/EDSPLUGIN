"""
HTTP client for the DHS Program API (api.dhsprogram.com).

Fetches indicators, countries, surveys, and indicator data.
"""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("edhs_core.dhs_api")

DHS_API_BASE = "https://api.dhsprogram.com/rest/dhs"


class DhsProgramApiClient:
    """
    Client for the DHS Program REST API.

    Requires an API key from https://api.dhsprogram.com/
    """

    def __init__(self, api_key: str, base_url: str = DHS_API_BASE) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str, **params: Any) -> str:
        """Build URL with API key and optional params."""
        params = {k: v for k, v in params.items() if v is not None}
        params["apiKey"] = self.api_key
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.base_url}/{path.lstrip('/')}?{qs}"

    def _get(self, path: str, **params: Any) -> Dict[str, Any]:
        """GET request to DHS Program API."""
        url = self._url(path, **params)
        with httpx.Client(timeout=60) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()

    def get_indicators(
        self,
        country_ids: Optional[str] = None,
        indicator_ids: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Fetch indicators catalog.

        Args:
            country_ids: Comma-separated country codes (e.g. ET,BJ)
            indicator_ids: Comma-separated indicator IDs
            page: Page number
            per_page: Results per page
        """
        params: Dict[str, Any] = {}
        if country_ids:
            params["countryIds"] = country_ids
        if indicator_ids:
            params["indicatorIds"] = indicator_ids
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perpage"] = per_page
        return self._get("indicators", **params)

    def get_countries(
        self,
        country_ids: Optional[str] = None,
        survey_ids: Optional[str] = None,
        survey_year: Optional[int] = None,
        survey_year_start: Optional[int] = None,
        survey_year_end: Optional[int] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Fetch countries with DHS surveys.
        """
        params: Dict[str, Any] = {}
        if country_ids:
            params["countryIds"] = country_ids
        if survey_ids:
            params["surveyIds"] = survey_ids
        if survey_year is not None:
            params["surveyYear"] = survey_year
        if survey_year_start is not None:
            params["surveyYearStart"] = survey_year_start
        if survey_year_end is not None:
            params["surveyYearEnd"] = survey_year_end
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perpage"] = per_page
        return self._get("countries", **params)

    def get_surveys(
        self,
        country_ids: Optional[str] = None,
        survey_ids: Optional[str] = None,
        survey_year: Optional[int] = None,
        survey_year_start: Optional[int] = None,
        survey_year_end: Optional[int] = None,
        survey_type: Optional[str] = None,
        indicator_ids: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Fetch surveys.
        """
        params: Dict[str, Any] = {}
        if country_ids:
            params["countryIds"] = country_ids
        if survey_ids:
            params["surveyIds"] = survey_ids
        if survey_year is not None:
            params["surveyYear"] = survey_year
        if survey_year_start is not None:
            params["surveyYearStart"] = survey_year_start
        if survey_year_end is not None:
            params["surveyYearEnd"] = survey_year_end
        if survey_type:
            params["surveyType"] = survey_type
        if indicator_ids:
            params["indicatorIds"] = indicator_ids
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perpage"] = per_page
        return self._get("surveys", **params)

    def get_data(
        self,
        country_ids: str,
        indicator_ids: str,
        survey_ids: Optional[str] = None,
        survey_year: Optional[int] = None,
        survey_year_start: Optional[int] = None,
        survey_year_end: Optional[int] = None,
        characteristic_ids: Optional[str] = None,
        breakdown: Optional[str] = None,
        return_geometry: Optional[bool] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Fetch indicator data (aggregated STATcompiler data).

        Args:
            country_ids: Comma-separated country codes (required)
            indicator_ids: Comma-separated indicator IDs (required)
            survey_ids: Optional survey IDs filter
            survey_year: Optional single year
            survey_year_start: Optional year range start
            survey_year_end: Optional year range end
            characteristic_ids: Optional characteristic filter
            breakdown: Optional breakdown variable
            return_geometry: Include geometry
            page: Page number
            per_page: Results per page
        """
        params: Dict[str, Any] = {
            "countryIds": country_ids,
            "indicatorIds": indicator_ids,
        }
        if survey_ids:
            params["surveyIds"] = survey_ids
        if survey_year is not None:
            params["surveyYear"] = survey_year
        if survey_year_start is not None:
            params["surveyYearStart"] = survey_year_start
        if survey_year_end is not None:
            params["surveyYearEnd"] = survey_year_end
        if characteristic_ids:
            params["characteristicIds"] = characteristic_ids
        if breakdown:
            params["breakdown"] = breakdown
        if return_geometry is not None:
            params["returnGeometry"] = str(return_geometry).lower()
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perpage"] = per_page
        return self._get("data", **params)
