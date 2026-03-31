"""
DHS Program API integration.

Proxies requests to https://api.dhsprogram.com/rest/dhs/ for:
- Indicators catalog
- Countries
- Surveys
- Indicator data (aggregated STATcompiler data)
"""

from .client import DhsProgramApiClient
from .country_codes import ISO3_TO_DHS_ALPHA2, countries_csv_to_dhs2
from .data_pipeline import dedupe_dhs_data_rows, process_dhs_data_response

__all__ = [
    "DhsProgramApiClient",
    "ISO3_TO_DHS_ALPHA2",
    "countries_csv_to_dhs2",
    "dedupe_dhs_data_rows",
    "process_dhs_data_response",
]
