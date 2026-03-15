"""
DHS Program API integration.

Proxies requests to https://api.dhsprogram.com/rest/dhs/ for:
- Indicators catalog
- Countries
- Surveys
- Indicator data (aggregated STATcompiler data)
"""

from .client import DhsProgramApiClient

__all__ = ["DhsProgramApiClient"]
