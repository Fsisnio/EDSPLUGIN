"""
Map common ISO 3166-1 alpha-3 codes to DHS / STATcompiler two-letter country codes.

The DHS Program REST API expects countryIds like ET, BJ, SN (alpha-2).
"""

from typing import Dict

# Expand over time as needed; unknown 3-letter codes fall back to first two characters.
ISO3_TO_DHS_ALPHA2: Dict[str, str] = {
    "ETH": "ET",
    "BEN": "BJ",
    "EGY": "EG",
    "GHA": "GH",
    "KEN": "KE",
    "NGA": "NG",
    "TZA": "TZ",
    "UGA": "UG",
    "ZAF": "ZA",
    "BFA": "BF",
    "MLI": "ML",
    "RWA": "RW",
    "SEN": "SN",
    "TCD": "TD",
    "CIV": "CI",
    "CMR": "CM",
    "COD": "CD",
    "COG": "CG",
    "MAR": "MA",
    "TUN": "TN",
    "ZMB": "ZM",
    "ZWE": "ZW",
    "MWI": "MW",
    "MOZ": "MZ",
    "NAM": "NA",
    "LSO": "LS",
    "SWZ": "SZ",
    "BDI": "BI",
    "SLE": "SL",
    "LBR": "LR",
    "NER": "NE",
    "MRT": "MR",
    "GIN": "GN",
    "GMB": "GM",
    "SOM": "SO",
}


def countries_csv_to_dhs2(country_ids: str) -> str:
    """
    Convert a comma-separated list of ISO3 or alpha-2 codes to DHS alpha-2 CSV.

    Examples:
        "SEN,KEN,BJ" -> "SN,KE,BJ"
        "SN,KE" -> "SN,KE"
    """
    parts = [p.strip().upper() for p in (country_ids or "").split(",") if p.strip()]
    out: list[str] = []
    for p in parts:
        if len(p) == 3 and p in ISO3_TO_DHS_ALPHA2:
            out.append(ISO3_TO_DHS_ALPHA2[p])
        elif len(p) == 2:
            out.append(p)
        elif len(p) > 3:
            out.append(p[:2])
        else:
            out.append(p)
    return ",".join(out)
