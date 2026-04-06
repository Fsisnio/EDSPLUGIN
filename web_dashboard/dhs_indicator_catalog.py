"""
Curated DHS Program STATcompiler indicators for the quick-fetch UI, grouped by topic.

Indicator IDs follow The DHS Program API; availability varies by country and survey year.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Category name -> list of (IndicatorId, short label for UI)
INDICATOR_CATALOG_BY_CATEGORY: Dict[str, List[Tuple[str, str]]] = {
    "Fertility & family planning": [
        ("FE_FRTR_W_TFR", "Total fertility rate (TFR)"),
        ("FE_FRTR_W_A15", "Age-specific fertility rate 15–19"),
        ("FP_CUSE_W_ANY", "Women using any contraceptive method"),
        ("FP_CUSE_W_MOD", "Women using modern contraceptive methods"),
        ("FP_UNMN_W_ANY", "Unmet need for family planning"),
    ],
    "Child mortality": [
        ("CM_ECMR_C_IMR", "Infant mortality rate"),
        ("CM_ECMR_C_U5M", "Under-five mortality rate"),
    ],
    "Maternal & newborn health": [
        ("RH_ANCN_W_ANY", "Women with at least one antenatal care visit"),
        ("RH_DEL_W_INST", "Births delivered in a health facility"),
        ("RH_DEL_W_SBA", "Births assisted by skilled birth attendant"),
    ],
    "Child health & nutrition": [
        ("CN_ANMC_C_ANY", "Children with any anemia"),
        ("CH_DIAR_C_ORS", "Children with diarrhea treated with ORS"),
        ("NT_STNT_C_HA2", "Children under 5 stunted"),
        ("NT_WAST_C_WH2", "Children under 5 wasted"),
        ("NT_UNDW_C_WA2", "Children under 5 underweight"),
    ],
    "Immunization": [
        ("CH_VACC_C_BCG", "Children receiving BCG vaccination"),
        ("CH_VACC_C_DPT3", "Children receiving 3 doses of DPT"),
        ("CH_VACC_C_MEAS", "Children vaccinated against measles"),
    ],
    "Malaria & HIV": [
        ("ML_NETS_H_OWN", "Households owning at least one mosquito net"),
        ("ML_FEVT_C_ADV", "Children with fever: advice or treatment sought"),
        ("ML_PMAL_C_RDT", "Malaria prevalence (RDT)"),
        ("HV_HIVP_A_PRE", "HIV prevalence among adults"),
    ],
}


def slug_category(category: str) -> str:
    """Stable key fragment for Streamlit widget keys."""
    s = re.sub(r"[^a-zA-Z0-9]+", "_", category.strip().lower())
    return s.strip("_")[:48] or "cat"


def format_option(indicator_id: str, label: str) -> str:
    """Single-line label shown in multiselects."""
    return f"{label} (`{indicator_id}`)"


def parse_option(option_str: str) -> str:
    """Extract IndicatorId from a format_option string."""
    if "`" in option_str:
        inner = option_str.rsplit("`", 2)
        if len(inner) >= 2:
            return inner[-2].strip()
    return option_str.split("(")[-1].rstrip(")").strip()


def all_catalog_pairs() -> List[Tuple[str, str]]:
    """Flatten (id, label) with stable order: category order, then item order."""
    out: List[Tuple[str, str]] = []
    for _cat, items in INDICATOR_CATALOG_BY_CATEGORY.items():
        out.extend(items)
    return out


def default_indicator_ids() -> List[str]:
    """Default selection for quick fetch (TFR + infant mortality)."""
    return ["FE_FRTR_W_TFR", "CM_ECMR_C_IMR"]
