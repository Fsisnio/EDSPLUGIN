"""
Streamlit MVP for the DHS Hybrid Plugin Platform.

Connects to the FastAPI backend to:
- Upload DHS/EDHS datasets (or create a mock session)
- Select country, indicator, and weighting
- Display indicator result, chart, and choropleth map
- Export results to CSV
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import pandas as pd
import requests
import streamlit as st

try:
    from dotenv import load_dotenv

    _APP_DIR = Path(__file__).resolve().parent
    load_dotenv(_APP_DIR.parent / ".env")
    load_dotenv(_APP_DIR / ".env")
except ImportError:
    pass

try:
    from edhs_core.dhs_api.country_codes import ISO3_TO_DHS_ALPHA2 as _ISO3_TO_DHS
except ImportError:
    _ISO3_TO_DHS: Dict[str, str] = {
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
    }

try:
    from dhs_research_features import (
        COMPARISON_TEMPLATES,
        INDICATOR_GLOSSARY,
        SUGGESTED_BY_TOPIC,
        chart_country_comparison_safe,
        chart_time_series_safe,
        chart_heatmap,
        chart_sankey,
        chart_radar,
        chart_box,
        chart_small_multiples,
        chart_treemap,
        chart_scatter,
        chart_gauge,
        chart_animated_time_series,
        chart_sunburst,
        export_excel,
        export_spss_sav,
        export_stata_ready,
        format_citation,
        build_shareable_params,
        get_dhs_dataframe,
    )
    _DHS_RESEARCH_AVAILABLE = True
except ImportError:
    _DHS_RESEARCH_AVAILABLE = False
    COMPARISON_TEMPLATES = []
    INDICATOR_GLOSSARY = {}
    SUGGESTED_BY_TOPIC = {}

    def get_dhs_dataframe(d):
        return pd.DataFrame(d.get("Data", []))

    def chart_time_series_safe(df):
        return None

    def chart_country_comparison_safe(df):
        return None

    def chart_heatmap(df, mode="country_indicator"):
        return None

    def chart_sankey(df):
        return None

    def chart_radar(df, country=None):
        return None

    def chart_box(df, by="Indicator"):
        return None

    def chart_small_multiples(df, facet_col="CountryName"):
        return None

    def chart_treemap(df):
        return None

    def chart_scatter(df, x_ind=None, y_ind=None):
        return None

    def chart_gauge(value, title="", min_val=0, max_val=100):
        return None

    def chart_animated_time_series(df):
        return None

    def chart_sunburst(df):
        return None

    def format_citation(*a, **k):
        return "Install dhs_research_features module for citations."

    def build_shareable_params(*a, **k):
        return ""

    def export_excel(*a, **k):
        raise ImportError("Install openpyxl")


    def export_stata_ready(df):
        return df.to_csv(index=False).encode("utf-8")

    def export_spss_sav(df):
        return None


def _format_indicator_value(v: Any) -> str:
    """Format indicator value for display. DHS values can be proportions (0-1), percentages (0-100), or rates per 1000."""
    if not isinstance(v, (int, float)) or pd.isna(v):
        return str(v)
    v = float(v)
    if 0 <= v <= 1:
        return f"{v * 100:.2f}%"
    if 1 < v <= 100:
        return f"{v:.1f}%"
    return f"{v:.1f}"  # Rate per 1000 or similar - no percent sign


def _render_dhs_research_ui(
    dhs_data: Dict[str, Any],
    countries: str,
    indicators: str,
    year_start: int,
    year_end: int,
    key_prefix: str = "dhs",
) -> None:
    """Render full DHS research UI: charts, citations, exports, glossary, saved configs."""
    df = get_dhs_dataframe(dhs_data) if _DHS_RESEARCH_AVAILABLE else pd.DataFrame(dhs_data.get("Data", []))
    if df.empty:
        st.info("No data returned for the selected filters.")
        return

    st.dataframe(df, use_container_width=True)

    if not _DHS_RESEARCH_AVAILABLE:
        st.caption("Install openpyxl for Excel export: pip install openpyxl")
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("Export CSV", data=csv_bytes, file_name="dhs_export.csv", mime="text/csv", key=f"{key_prefix}_csv")
        return

    # --- Visualizations ---
    st.markdown("---")
    st.subheader("📊 Visualizations")
    viz_col1, viz_col2 = st.columns(2)
    with viz_col1:
        fig_ts = chart_time_series_safe(df)
        if fig_ts:
            st.plotly_chart(fig_ts, use_container_width=True, key=f"{key_prefix}_ts")
        else:
            st.caption("No time series data to plot.")
    with viz_col2:
        fig_cc = chart_country_comparison_safe(df)
        if fig_cc:
            st.plotly_chart(fig_cc, use_container_width=True, key=f"{key_prefix}_cc")
        else:
            st.caption("No comparison data to plot.")

    # --- Gauge / KPI cards ---
    if "Value" in df.columns and len(df) >= 1:
        st.markdown("#### Key indicators")
        st.caption("Latest values by indicator and country")
        kpi_vals = df.nlargest(5, "SurveyYear" if "SurveyYear" in df.columns else "Value") if "SurveyYear" in df.columns else df.head(5)
        kpi_cols = st.columns(min(5, len(kpi_vals)))
        for i, (_, row) in enumerate(kpi_vals.iterrows()):
            with kpi_cols[i]:
                v = row.get("Value", 0)
                lbl = str(row.get("Indicator", row.get("IndicatorId", "Value")))
                subtitle_parts = []
                if "CountryName" in row and pd.notna(row.get("CountryName")):
                    subtitle_parts.append(str(row["CountryName"]))
                if "SurveyYear" in row and pd.notna(row.get("SurveyYear")):
                    subtitle_parts.append(str(int(row["SurveyYear"])))
                subtitle = " · ".join(subtitle_parts) if subtitle_parts else ""
                fig_g = chart_gauge(
                    float(v), lbl,
                    min_val=0,
                    max_val=max(100, float(v) * 1.2) if isinstance(v, (int, float)) else 100,
                    subtitle=subtitle,
                )
                if fig_g:
                    st.plotly_chart(fig_g, use_container_width=True, key=f"{key_prefix}_gauge_{i}")

    # --- More visualizations (selectable) ---
    with st.expander("📈 More visualizations", expanded=True):
        viz_type = st.selectbox(
            "Chart type",
            [
                "Heatmap (country × indicator)",
                "Heatmap (year × indicator)",
                "Sankey (Country → Indicator)",
                "Radar (country profile)",
                "Box plot (by indicator)",
                "Box plot (by country)",
                "Small multiples (by country)",
                "Small multiples (by year)",
                "Treemap",
                "Scatter (two indicators)",
                "Animated time series",
                "Sunburst",
            ],
            key=f"{key_prefix}_viz_type",
        )
        fig_extra = None
        try:
            if viz_type.startswith("Heatmap (country"):
                fig_extra = chart_heatmap(df, mode="country_indicator")
            elif viz_type.startswith("Heatmap (year"):
                fig_extra = chart_heatmap(df, mode="year_indicator")
            elif viz_type.startswith("Sankey"):
                fig_extra = chart_sankey(df)
            elif viz_type.startswith("Radar"):
                countries_list = ([""] + df["CountryName"].unique().tolist()) if "CountryName" in df.columns else [""]
                country_opt = st.selectbox("Country for radar profile", options=countries_list, key=f"{key_prefix}_radar_country")
                fig_extra = chart_radar(df, country=country_opt or None)
            elif viz_type == "Box plot (by indicator)":
                fig_extra = chart_box(df, by="Indicator")
            elif viz_type == "Box plot (by country)":
                fig_extra = chart_box(df, by="country")
            elif viz_type == "Small multiples (by country)":
                fig_extra = chart_small_multiples(df, facet_col="country")
            elif viz_type == "Small multiples (by year)":
                fig_extra = chart_small_multiples(df, facet_col="year")
            elif viz_type == "Treemap":
                fig_extra = chart_treemap(df)
            elif viz_type == "Scatter (two indicators)":
                fig_extra = chart_scatter(df)
            elif viz_type == "Animated time series":
                fig_extra = chart_animated_time_series(df)
            elif viz_type == "Sunburst":
                fig_extra = chart_sunburst(df)
        except Exception as e:
            st.caption(f"Chart not available: {e}")
        if fig_extra:
            st.plotly_chart(fig_extra, use_container_width=True, key=f"{key_prefix}_extra")
        else:
            st.caption("No data for this chart type.")

    # --- Methodology notes ---
    with st.expander("📋 Methodology notes", expanded=False):
        st.markdown(
            "Data from **The DHS Program STATcompiler** (api.dhsprogram.com). "
            "Indicators are computed from nationally representative household surveys. "
            "Sampling weights are applied. See [dhsprogram.com](https://dhsprogram.com) for methodology."
        )

    # --- Citation & Shareable URL ---
    st.subheader("📚 Citation & Reproducibility")
    cite_style = st.selectbox("Citation style", ["apa", "chicago", "harvard"], key=f"{key_prefix}_cite_style")
    citation = format_citation(countries, indicators, year_start, year_end, cite_style)
    st.text_area("Citation", value=citation, height=80, key=f"{key_prefix}_citation")
    st.caption("Copy for your paper or report.")
    params = build_shareable_params(countries, indicators, year_start, year_end)
    share_url = f"?{params}"
    st.text_input("Shareable link", value=share_url, key=f"{key_prefix}_share", disabled=True)

    # --- Export ---
    st.subheader("📥 Export")
    meta = {"countries": countries, "indicators": indicators, "year_start": year_start, "year_end": year_end}
    exp_col1, exp_col2, exp_col3, exp_col4 = st.columns(4)
    with exp_col1:
        st.download_button("CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="dhs_export.csv", mime="text/csv", key=f"{key_prefix}_dl_csv")
    with exp_col2:
        try:
            xl = export_excel(df, meta)
            st.download_button("Excel", data=xl, file_name="dhs_export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"{key_prefix}_dl_xl")
        except Exception:
            st.caption("Excel: install openpyxl")
    with exp_col3:
        st.download_button("Stata CSV", data=export_stata_ready(df), file_name="dhs_stata_ready.csv", mime="text/csv", key=f"{key_prefix}_dl_stata")
    with exp_col4:
        sav = export_spss_sav(df)
        if sav:
            st.download_button("SPSS .sav", data=sav, file_name="dhs_export.sav", mime="application/octet-stream", key=f"{key_prefix}_dl_sav")
        else:
            st.caption("SPSS: install pyreadstat")

    # --- Indicator glossary ---
    st.subheader("📖 Indicator glossary")
    ind_ids = [x.strip() for x in indicators.split(",") if x.strip()]
    for iid in ind_ids[:5]:
        if iid in INDICATOR_GLOSSARY:
            g = INDICATOR_GLOSSARY[iid]
            with st.expander(f"{iid}: {g.get('name', iid)}", expanded=False):
                st.markdown(f"**Definition:** {g.get('definition', '—')}")
                if g.get("formula"):
                    st.markdown(f"**Formula:** {g['formula']}")
                if g.get("interpretation"):
                    st.markdown(f"**Interpretation:** {g['interpretation']}")
        else:
            st.caption(f"{iid}: No glossary entry (browse catalog for more).")


# -----------------------------------------------------------------------------
# Configuration and API client
# -----------------------------------------------------------------------------

def _to_dhs_country_code(raw: str) -> str:
    """Convert country input (2- or 3-letter) to DHS 2-letter code."""
    s = (raw or "").strip().upper()
    if not s:
        return "ET"
    if len(s) >= 3 and s in _ISO3_TO_DHS:
        return _ISO3_TO_DHS[s]
    return s[:2]


_DHS_ISO3_MULTI_OPTIONS: List[str] = sorted(_ISO3_TO_DHS.keys())
_DHS_QUICK_INDICATOR_PRESETS: List[Tuple[str, str]] = [
    ("Total fertility rate (TFR)", "FE_FRTR_W_TFR"),
    ("Infant mortality rate", "CM_ECMR_C_IMR"),
    ("Under-five mortality", "CM_ECMR_C_U5M"),
    ("Modern contraception (women)", "FP_CUSE_W_MOD"),
]


def get_headers(
    tenant_id: str,
    bearer_token: Optional[str],
    dhs_api_key: Optional[str] = None,
) -> Dict[str, str]:
    h = {"X-Tenant-ID": tenant_id}
    if bearer_token:
        h["Authorization"] = f"Bearer {bearer_token}"
    if dhs_api_key and dhs_api_key.strip():
        h["X-DHS-API-Key"] = dhs_api_key.strip()
    return h


# STATcompiler / DHS Program API indicator IDs → pluggable microdata indicator `id` (see edhs_core.indicators).
DHS_API_INDICATOR_TO_MICRODATA: Dict[str, str] = {
    "FE_FRTR_W_A15": "total_fertility_rate",
    "FE_FRTR_W_TFR": "total_fertility_rate",
    "CN_ANMC_C_ANY": "modern_contraception_rate",
    "CN_ANMC_W_ANY": "modern_contraception_rate",
    "CN_ANMC_C_MOD": "modern_contraception_rate",
    "CN_NUTS_C_HA2": "stunting_prevalence",
    "CN_NUTR_C_HA2": "stunting_prevalence",
}


def _first_iso_from_dhs_fetch_csv(s: Optional[str]) -> Optional[str]:
    if not s or not str(s).strip():
        return None
    first = str(s).split(",")[0].strip().upper()
    if len(first) < 2:
        return None
    return first[:3]


def _map_dhs_api_indicator_to_microdata_id(dhs_id: str) -> Optional[str]:
    u = dhs_id.strip().upper()
    if u in DHS_API_INDICATOR_TO_MICRODATA:
        return DHS_API_INDICATOR_TO_MICRODATA[u]
    if u.startswith("FE_FRTR"):
        return "total_fertility_rate"
    if "ANMC" in u or u.startswith("CN_CP"):
        return "modern_contraception_rate"
    if "NUTS" in u or "HA2" in u:
        return "stunting_prevalence"
    return None


def _first_micro_indicator_from_dhs_fetch(csv_ids: Optional[str]) -> Optional[str]:
    if not csv_ids:
        return None
    for part in str(csv_ids).split(","):
        m = _map_dhs_api_indicator_to_microdata_id(part.strip())
        if m:
            return m
    return None


def _microdata_country_default_from_state() -> str:
    sc = st.session_state.get("edhs_survey_country_code")
    if sc:
        return str(sc).strip().upper()[:3]
    fc = st.session_state.get("edhs_dhs_fetch_countries")
    iso = _first_iso_from_dhs_fetch_csv(str(fc) if fc else "")
    if iso:
        return iso
    return "ETH"


def _normalize_backend_base_url(raw: str) -> str:
    """
    Strip query/fragment and trailing slash so pasted URLs still work as a path prefix
    (e.g. .../api/v1?utm=x → .../api/v1). Fully customizable host/path for your deployment.
    """
    s = (raw or "").strip()
    if not s:
        return ""
    if "://" not in s:
        s = "http://" + s
    p = urlparse(s)
    path = (p.path or "").rstrip("/")
    return urlunparse((p.scheme, p.netloc, path, "", "", ""))


def _raise_for_status_with_detail(r: requests.Response) -> None:
    """Call raise_for_status; on error include FastAPI `detail` in the message (Streamlit users otherwise only see a generic 404 URL)."""
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        detail: Any = None
        try:
            body = r.json()
            detail = body.get("detail")
        except Exception:
            pass
        if detail is not None:
            if isinstance(detail, list):
                extra = repr(detail)
            else:
                extra = str(detail)
            raise requests.HTTPError(
                f"{e}\nServer detail: {extra}",
                response=r,
            ) from None
        raise


def _require_edhs_backend_base_url(base_url: str) -> None:
    """
    Microdata and /dhs-api proxy calls must use this app's FastAPI base (…/api/v1),
    not a raw https://api.dhsprogram.com/... URL — otherwise paths like /indicators/compute
    get appended to the query string (broken apiKey=…/indicators/compute) and return 405.
    """
    normalized = _normalize_backend_base_url(base_url)
    if not normalized:
        raise ValueError("API base URL is empty. Set it under Backend connection.")
    parsed = urlparse(normalized if "://" in normalized else f"http://{normalized}")
    host = (parsed.hostname or "").lower()
    path_l = (parsed.path or "").lower()
    if "dhsprogram.com" in host:
        raise ValueError(
            "This field must be **your** EDHS/FastAPI server base URL "
            "(e.g. `http://127.0.0.1:8000/api/v1`, `https://your-service.onrender.com/api/v1`, or any host/port you deploy). "
            "It must **not** be the public `api.dhsprogram.com` URL or a sample `/rest/dhs/data?…` link — "
            "those are for the DHS catalog; enter your key under *DHS API key*. Update *Backend connection*."
        )
    if "/rest/dhs" in path_l:
        raise ValueError(
            "You likely pasted a **DHS Program request URL** (`/rest/dhs/...`). "
            "Enter only the **root of your EDHS API** (e.g. `http://127.0.0.1:8000/api/v1`), "
            "not the STATcompiler URL."
        )


def api_health(
    base_url: str,
    tenant_id: str,
    bearer_token: Optional[str],
    dhs_api_key: Optional[str] = None,
) -> bool:
    try:
        _require_edhs_backend_base_url(base_url)
        r = requests.get(
            f"{base_url}/health",
            headers=get_headers(tenant_id, bearer_token, dhs_api_key),
            timeout=5,
        )
        return r.status_code == 200
    except Exception:
        return False


def api_list_indicators(
    base_url: str, tenant_id: str, bearer_token: Optional[str]
) -> List[Dict[str, Any]]:
    _require_edhs_backend_base_url(base_url)
    r = requests.get(
        f"{base_url}/indicators",
        headers=get_headers(tenant_id, bearer_token),
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("indicators", [])


def api_upload(
    base_url: str,
    tenant_id: str,
    bearer_token: Optional[str],
    file_bytes: bytes,
    filename: str,
    *,
    survey_country_code: Optional[str] = None,
    survey_year: Optional[int] = None,
    survey_type: Optional[str] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if survey_country_code:
        data["survey_country_code"] = survey_country_code
    if survey_year is not None:
        data["survey_year"] = str(survey_year)
    if survey_type:
        data["survey_type"] = survey_type
    _require_edhs_backend_base_url(base_url)
    r = requests.post(
        f"{base_url}/sessions/upload",
        headers=get_headers(tenant_id, bearer_token),
        files={"file": (filename, file_bytes)},
        data=data if data else None,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def api_session_from_url(
    base_url: str,
    tenant_id: str,
    bearer_token: Optional[str],
    dataset_url: str,
    *,
    survey_country_code: Optional[str] = None,
    survey_year: Optional[int] = None,
    survey_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a session by loading data from an external URL (.dta, .sav, or .zip)."""
    payload: Dict[str, Any] = {"dataset_url": dataset_url.strip()}
    if survey_country_code:
        payload["survey_country_code"] = survey_country_code
    if survey_year is not None:
        payload["survey_year"] = survey_year
    if survey_type:
        payload["survey_type"] = survey_type
    _require_edhs_backend_base_url(base_url)
    r = requests.post(
        f"{base_url}/sessions/from-url",
        headers={**get_headers(tenant_id, bearer_token), "Content-Type": "application/json"},
        json=payload,
        timeout=150,
    )
    r.raise_for_status()
    return r.json()


def api_mock_session(
    base_url: str,
    tenant_id: str,
    bearer_token: Optional[str],
    *,
    survey_country_code: Optional[str] = None,
    survey_year: Optional[int] = None,
    survey_type: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, str] = {}
    if survey_country_code:
        params["survey_country_code"] = survey_country_code
    if survey_year is not None:
        params["survey_year"] = str(survey_year)
    if survey_type:
        params["survey_type"] = survey_type
    _require_edhs_backend_base_url(base_url)
    r = requests.post(
        f"{base_url}/test/mock-session",
        headers=get_headers(tenant_id, bearer_token),
        params=params if params else None,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def api_compute_indicator(
    base_url: str,
    tenant_id: str,
    bearer_token: Optional[str],
    session_id: str,
    indicator_id: str,
    use_weights: bool,
    weight_var: str,
) -> Dict[str, Any]:
    _require_edhs_backend_base_url(base_url)
    r = requests.post(
        f"{base_url}/indicators/compute",
        headers={**get_headers(tenant_id, bearer_token), "Content-Type": "application/json"},
        json={
            "session_id": session_id,
            "indicator_id": indicator_id,
            "use_weights": use_weights,
            "weight_var": weight_var,
            "extra_params": {},
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["result"]


def api_compute_grouped(
    base_url: str,
    tenant_id: str,
    bearer_token: Optional[str],
    session_id: str,
    indicator_id: str,
    group_by_column: str,
    use_weights: bool,
    weight_var: str,
) -> Dict[str, Any]:
    _require_edhs_backend_base_url(base_url)
    r = requests.post(
        f"{base_url}/indicators/compute-grouped",
        headers={**get_headers(tenant_id, bearer_token), "Content-Type": "application/json"},
        json={
            "session_id": session_id,
            "indicator_id": indicator_id,
            "group_by_column": group_by_column,
            "use_weights": use_weights,
            "weight_var": weight_var,
            "extra_params": {},
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def api_dhs_indicators(
    base_url: str,
    tenant_id: str,
    bearer_token: Optional[str],
    country_ids: Optional[str] = None,
    indicator_ids: Optional[str] = None,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    dhs_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """List indicators from DHS Program API (via backend proxy)."""
    _require_edhs_backend_base_url(base_url)
    params: Dict[str, Any] = {}
    if country_ids:
        params["country_ids"] = country_ids
    if indicator_ids:
        params["indicator_ids"] = indicator_ids
    if page is not None:
        params["page"] = page
    if per_page is not None:
        params["perpage"] = per_page
    r = requests.get(
        f"{base_url}/dhs-api/indicators",
        headers=get_headers(tenant_id, bearer_token, dhs_api_key),
        params=params if params else None,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def api_dhs_countries(
    base_url: str,
    tenant_id: str,
    bearer_token: Optional[str],
    dhs_api_key: Optional[str] = None,
    **params: Any,
) -> Dict[str, Any]:
    """List countries from DHS Program API (via backend proxy)."""
    _require_edhs_backend_base_url(base_url)
    r = requests.get(
        f"{base_url}/dhs-api/countries",
        headers=get_headers(tenant_id, bearer_token, dhs_api_key),
        params={k: v for k, v in params.items() if v is not None},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def api_dhs_data(
    base_url: str,
    tenant_id: str,
    bearer_token: Optional[str],
    country_ids: str,
    indicator_ids: str,
    survey_year_start: Optional[int] = None,
    survey_year_end: Optional[int] = None,
    dhs_api_key: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Fetch indicator data from DHS Program API (via backend proxy)."""
    payload: Dict[str, Any] = {
        "country_ids": country_ids,
        "indicator_ids": indicator_ids,
        **{k: v for k, v in kwargs.items() if v is not None},
    }
    if survey_year_start is not None:
        payload["survey_year_start"] = survey_year_start
    if survey_year_end is not None:
        payload["survey_year_end"] = survey_year_end
    _require_edhs_backend_base_url(base_url)
    r = requests.get(
        f"{base_url}/dhs-api/data",
        headers=get_headers(tenant_id, bearer_token, dhs_api_key),
        params=payload,
        timeout=90,
    )
    r.raise_for_status()
    return r.json()


def api_dhs_data_fetch(
    base_url: str,
    tenant_id: str,
    bearer_token: Optional[str],
    country_ids: str,
    indicator_ids: str,
    survey_year_start: Optional[int] = None,
    survey_year_end: Optional[int] = None,
    dhs_api_key: Optional[str] = None,
    *,
    breakdown: Optional[str] = None,
    post_filter_years: bool = True,
    dedupe: bool = True,
) -> Dict[str, Any]:
    """
    DHS STATcompiler data: one GET via backend /dhs-api/data/fetch with ISO3→DHS2 mapping
    and post-filter / dedupe on the Data array.
    """
    payload: Dict[str, Any] = {
        "country_ids": country_ids,
        "indicator_ids": indicator_ids,
        "post_filter_years": post_filter_years,
        "dedupe": dedupe,
    }
    if survey_year_start is not None:
        payload["survey_year_start"] = survey_year_start
    if survey_year_end is not None:
        payload["survey_year_end"] = survey_year_end
    if breakdown:
        payload["breakdown"] = breakdown
    _require_edhs_backend_base_url(base_url)
    r = requests.get(
        f"{base_url}/dhs-api/data/fetch",
        headers=get_headers(tenant_id, bearer_token, dhs_api_key),
        params=payload,
        timeout=90,
    )
    r.raise_for_status()
    return r.json()


def api_spatial_aggregate(
    base_url: str,
    tenant_id: str,
    bearer_token: Optional[str],
    session_id: str,
    indicator_id: str,
    country_code: str,
    admin_level: int,
    microdata_admin_column: str,
    boundary_admin_column: str,
    use_weights: bool,
    weight_var: str,
) -> Dict[str, Any]:
    _require_edhs_backend_base_url(base_url)
    r = requests.post(
        f"{base_url}/spatial/aggregate",
        headers={**get_headers(tenant_id, bearer_token), "Content-Type": "application/json"},
        json={
            "session_id": session_id,
            "indicator_id": indicator_id,
            "country_code": country_code,
            "admin_level": admin_level,
            "microdata_admin_column": microdata_admin_column,
            "boundary_admin_column": boundary_admin_column,
            "use_weights": use_weights,
            "weight_var": weight_var,
            "extra_indicator_params": {},
        },
        timeout=120,
    )
    _raise_for_status_with_detail(r)
    return r.json()


# -----------------------------------------------------------------------------
# Choropleth map (Folium)
# -----------------------------------------------------------------------------

def render_choropleth(geojson: Dict[str, Any], value_key: str = "value") -> str:
    try:
        import folium
        from folium.features import GeoJsonTooltip
    except ImportError:
        return "<p>Install <code>folium</code> for map view: <code>pip install folium</code></p>"

    features = geojson.get("features", [])
    if not features:
        return "<p>No features to display.</p>"

    # Bounds from first geometry (simple center)
    m = folium.Map(location=[9, 40], zoom_start=4, tiles="CartoDB positron")

    def style_fn(x):
        props = x.get("properties", {})
        v = props.get(value_key)
        if v is None:
            return {"fillColor": "#ccc", "fillOpacity": 0.5, "weight": 1}
        # Simple green gradient 0->1
        r, g = 0, int(200 * min(1, max(0, float(v))))
        return {
            "fillColor": f"#{r:02x}{g:02x}80",
            "fillOpacity": 0.7,
            "weight": 1,
            "color": "#333",
        }

    tooltip = GeoJsonTooltip(
        fields=["admin_id", value_key, "population_n"],
        aliases=["Admin", "Value", "N"],
        localize=True,
    )

    folium.GeoJson(
        geojson,
        style_function=style_fn,
        tooltip=tooltip,
    ).add_to(m)

    return m._repr_html_()


# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="DHS Hybrid Plugin Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Google Analytics (G-X76TEN0BS5): injected into Streamlit's index.html at build time
# (see scripts/inject_streamlit_google_analytics.py) — not here, iframe would hide from Tag Assistant.

# -----------------------------------------------------------------------------
# Custom CSS – modern, user-friendly styling
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* Typography & spacing */
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
    html, body, [data-testid="stAppViewContainer"] { font-family: 'DM Sans', system-ui, sans-serif; }
    
    /* Header styling */
    .edhs-header {
        background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 14px rgba(13, 148, 136, 0.25);
        text-align: center;
    }
    .edhs-header h1 { margin: 0; font-size: 1.75rem; font-weight: 700; }
    .edhs-header p { margin: 0.35rem 0 0; opacity: 0.95; font-size: 0.95rem; }
    
    /* Card-style sections */
    .edhs-card {
        background: white;
        border-radius: 10px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
    }
    
    /* Sidebar nav styling */
    [data-testid="stSidebar"] .stRadio > label { font-weight: 600; font-size: 0.9rem; }
    [data-testid="stSidebar"] section[data-testid="stSidebar"] { padding-top: 0.5rem; }
    
    /* Button polish */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
        cursor: pointer;
        border: 1px solid #e2e8f0;
        background-color: #fff;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(13, 148, 136, 0.2);
        border-color: #0d9488;
        background-color: #f0fdfa;
        color: #0f766e;
    }
    .stButton > button:active {
        transform: translateY(0);
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Metric / KPI cards */
    [data-testid="stMetric"] { background: #f8fafc; padding: 0.75rem; border-radius: 8px; }
    
    /* Section headers */
    h3 { color: #0f766e; font-weight: 600; }
    
    /* Hide Streamlit branding in compact mode */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# Process pending navigation (before any widget using edhs_nav_radio is created)
if "edhs_nav_pending" in st.session_state:
    st.session_state["edhs_nav_page"] = st.session_state.pop("edhs_nav_pending")
    st.session_state.pop("edhs_nav_radio", None)  # Let radio use index from edhs_nav_page

# -----------------------------------------------------------------------------
# Sidebar: Navigation menu
# -----------------------------------------------------------------------------
st.sidebar.markdown("### 📊 DHS Hybrid Plugin Platform")
st.sidebar.markdown("---")

nav_options = ["🏠 Home", "📖 Onboarding", "📡 DHS Program API", "📋 DHS Indicators", "📂 Microdata Analysis", "📊 Custom Dashboard", "⚙️ Settings"]
if "edhs_nav_page" not in st.session_state:
    st.session_state["edhs_nav_page"] = "🏠 Home"

_current = st.session_state.get("edhs_nav_page", nav_options[0])
_nav_index = nav_options.index(_current) if _current in nav_options else 0
nav_choice = st.sidebar.radio(
    "**Navigate**",
    nav_options,
    index=_nav_index,
    key="edhs_nav_radio",
    label_visibility="collapsed",
)
st.session_state["edhs_nav_page"] = nav_choice

st.sidebar.markdown("---")

# Default API URL: from env (Render) or localhost
def _default_api_base_url() -> str:
    if base := os.environ.get("API_BASE_URL"):
        return base.rstrip("/")
    host = os.environ.get("API_HOST")
    port = os.environ.get("API_PORT")
    if host and port:
        return f"http://{host}:{port}/api/v1"
    return "http://127.0.0.1:8000/api/v1"


def _hide_backend_connection_ui() -> bool:
    """
    Skip the Backend connection form when the host preconfigures the API.

    - EDHS_SHOW_BACKEND_CONNECTION=true: always show (debug).
    - EDHS_HIDE_BACKEND_CONNECTION=true: hide.
    - API_BASE_URL set (e.g. Render): hide so end users do not change the URL.
    """
    if os.environ.get("EDHS_SHOW_BACKEND_CONNECTION", "").strip().lower() in ("1", "true", "yes"):
        return False
    if os.environ.get("EDHS_HIDE_BACKEND_CONNECTION", "").strip().lower() in ("1", "true", "yes"):
        return True
    if (os.environ.get("API_BASE_URL") or "").strip():
        return True
    return False


def _hide_choropleth_ui() -> bool:
    """
    Hide map / spatial aggregation controls when admin boundary GeoPackages are not deployed.

    Set EDHS_HIDE_CHOROPLETH=true (e.g. on Render) to avoid 404s on /spatial/aggregate.
    EDHS_SHOW_CHOROPLETH=true forces the controls visible (overrides hide).
    """
    if os.environ.get("EDHS_SHOW_CHOROPLETH", "").strip().lower() in ("1", "true", "yes"):
        return False
    return os.environ.get("EDHS_HIDE_CHOROPLETH", "").strip().lower() in ("1", "true", "yes")


if _hide_backend_connection_ui():
    base_url = _normalize_backend_base_url(_default_api_base_url())
    tenant_id = (os.environ.get("EDHS_TENANT_ID") or "demo-tenant").strip() or "demo-tenant"
    _bt = (os.environ.get("EDHS_JWT_TOKEN") or "").strip()
    bearer_token: Optional[str] = _bt if _bt else None
    _dk = (os.environ.get("EDHS_STREAMLIT_DHS_API_KEY") or "").strip()
    dhs_api_key: Optional[str] = _dk if _dk else None
    st.sidebar.caption("Backend API is preconfigured for this deployment.")
else:
    with st.sidebar.expander("Backend connection", expanded=False):
        if "edhs_api_base_url" not in st.session_state:
            st.session_state["edhs_api_base_url"] = _default_api_base_url()
        st.text_input(
            "Backend base URL",
            key="edhs_api_base_url",
            help=(
                "Fully customizable: root of **your** EDHS/FastAPI API (localhost, Render, IP, custom domain, `/api/v1` path). "
                "Not `api.dhsprogram.com` or a `/rest/dhs/data?…` sample URL — use *DHS API key* for your DHS key."
            ),
        )
        base_url = _normalize_backend_base_url(st.session_state.get("edhs_api_base_url") or "")
        tenant_id = st.text_input("Tenant ID", value="demo-tenant")
        bearer_token = st.text_input(
            "JWT token (optional)",
            type="password",
            help="Bearer token for authenticated deployments.",
        )
        dhs_api_key = st.text_input(
            "DHS API key (optional)",
            type="password",
            placeholder="Use your own key from api.dhsprogram.com",
            help="Override the backend's DHS Program API key. Leave empty to use the server default.",
        )
        if st.button("Check connection"):
            try:
                _require_edhs_backend_base_url(base_url)
            except ValueError as err:
                st.session_state["edhs_connection_ok"] = False
                st.error(str(err))
            else:
                ok = api_health(base_url, tenant_id, bearer_token or None, dhs_api_key or None)
                st.session_state["edhs_connection_ok"] = ok
                if ok:
                    st.success("Backend is reachable.")
                else:
                    st.error("Cannot reach backend. Check URL and tenant.")

# Connection status badge (lazy check on first load)
_health_timeout = float(os.environ.get("EDHS_HEALTHCHECK_TIMEOUT", "10"))
if "edhs_connection_ok" not in st.session_state:
    try:
        _require_edhs_backend_base_url(base_url)
        r = requests.get(
            f"{base_url}/health",
            headers=get_headers(tenant_id, bearer_token or None, dhs_api_key or None),
            timeout=_health_timeout,
        )
        st.session_state["edhs_connection_ok"] = r.status_code == 200
    except Exception:
        st.session_state["edhs_connection_ok"] = False
if st.session_state.get("edhs_connection_ok"):
    st.sidebar.caption("🟢 Backend connected")
else:
    st.sidebar.caption("🔴 Backend not reached")
    if _hide_backend_connection_ui():
        st.sidebar.caption(
            "API should run on port 8000 in the same Docker container. "
            "In Render: clear **Docker Command** (use Dockerfile `CMD`), open **Logs** and confirm Uvicorn starts."
        )

st.sidebar.divider()
st.sidebar.subheader("Dataset / session")

session_id: Optional[str] = st.session_state.get("edhs_session_id")

# Survey metadata (optional) for new sessions
st.sidebar.caption("Survey metadata (optional)")
meta_col1, meta_col2 = st.sidebar.columns(2)
with meta_col1:
    sidebar_country = st.text_input("Country (ISO)", value="ETH", key="sidebar_country", max_chars=3)
    sidebar_year = st.number_input("Year", min_value=1990, max_value=2030, value=2019, step=1, key="sidebar_year")
with meta_col2:
    sidebar_type = st.selectbox("Type", ["DHS", "MIS", "AIS", "Other"], key="sidebar_type")

# Fetch data for selected country from DHS API (no sample data)
country_code_dhs = _to_dhs_country_code(sidebar_country or "ET")
st.sidebar.caption("Don't want sample data? Load data for your selected country:")
if st.sidebar.button(f"Fetch data for {country_code_dhs or 'country'} from DHS API", key="dhs_fetch_for_country"):
    try:
        with st.sidebar.spinner(f"Fetching data for {country_code_dhs}…"):
            dhs_resp = api_dhs_data_fetch(
                base_url,
                tenant_id,
                bearer_token or None,
                country_ids=(sidebar_country or "ETH").strip().upper(),
                indicator_ids="FE_FRTR_W_A15,CN_ANMC_C_ANY",
                dhs_api_key=dhs_api_key or None,
                survey_year_start=2000,
                survey_year_end=2024,
            )
        st.session_state["edhs_dhs_api_data"] = dhs_resp
        st.session_state["edhs_dhs_fetch_countries"] = (sidebar_country or "ETH").strip().upper()
        st.session_state["edhs_dhs_fetch_indicators"] = "FE_FRTR_W_A15,CN_ANMC_C_ANY"
        st.sidebar.success(f"Loaded {len(dhs_resp.get('Data', []))} records for {country_code_dhs}. See DHS Program API section below.")
        st.rerun()
    except Exception as e:
        st.sidebar.error(str(e))

st.sidebar.caption("Or use sample data (Benin microdata):")
# Try with sample data (clearer label)
if st.sidebar.button("Try with sample data (Benin BJBR71FL.DTA if available)", type="primary"):
    try:
        resp = api_mock_session(
            base_url, tenant_id, bearer_token or None,
            survey_country_code=sidebar_country.strip() or None,
            survey_year=int(sidebar_year),
            survey_type=sidebar_type if sidebar_type != "Other" else "DHS",
        )
        st.session_state["edhs_session_id"] = resp["session_id"]
        st.session_state["edhs_session_source"] = "sample"
        st.session_state["edhs_survey_country_code"] = resp.get("survey_country_code")
        st.session_state["edhs_survey_year"] = resp.get("survey_year")
        st.session_state["edhs_survey_type"] = resp.get("survey_type")
        # Keep history of sessions for multi-country comparisons
        history = st.session_state.setdefault("edhs_sessions_history", [])
        history.append(
            {
                "session_id": resp["session_id"],
                "country": resp.get("survey_country_code"),
                "year": resp.get("survey_year"),
                "type": resp.get("survey_type"),
                "filename": resp.get("filename", "sample"),
            }
        )
        st.sidebar.success(f"Session ready: `{resp['session_id'][:12]}…`")
        st.rerun()
    except Exception as e:
        st.sidebar.error(str(e))

# Import from external API / URL
st.sidebar.caption(
    "Or load data directly from a URL (.dta, .sav, or .zip). "
    "For DHS Program: prefer the **SPSS** (.sav) download link (filename ends with SV.ZIP) if the Stata link fails."
)
url_import_url = st.sidebar.text_input(
    "Dataset URL",
    value=st.session_state.get("edhs_url_import_value", ""),
    key="url_import_input",
    placeholder="https://… .dta, .sav, or .zip",
    label_visibility="collapsed",
)
if st.sidebar.button("Load from URL", type="primary", key="load_from_url_btn"):
    if not (url_import_url and url_import_url.strip().startswith(("http://", "https://"))):
        st.sidebar.error("Enter a valid http(s) URL to a .dta, .sav, or .zip file.")
    else:
        try:
            with st.sidebar.spinner("Downloading and creating session…"):
                resp = api_session_from_url(
                    base_url,
                    tenant_id,
                    bearer_token or None,
                    url_import_url.strip(),
                    survey_country_code=sidebar_country.strip() or None,
                    survey_year=int(sidebar_year),
                    survey_type=sidebar_type if sidebar_type != "Other" else None,
                )
            st.session_state["edhs_session_id"] = resp["session_id"]
            st.session_state["edhs_session_source"] = "url"
            st.session_state["edhs_survey_country_code"] = resp.get("survey_country_code")
            st.session_state["edhs_survey_year"] = resp.get("survey_year")
            st.session_state["edhs_survey_type"] = resp.get("survey_type")
            history = st.session_state.setdefault("edhs_sessions_history", [])
            history.append(
                {
                    "session_id": resp["session_id"],
                    "country": resp.get("survey_country_code"),
                    "year": resp.get("survey_year"),
                    "type": resp.get("survey_type"),
                    "filename": resp.get("filename", "from_url"),
                }
            )
            st.sidebar.success(f"Session from URL: `{resp['session_id'][:12]}…`")
            st.rerun()
        except requests.HTTPError as e:
            detail = str(e)
            if e.response is not None:
                try:
                    body = e.response.json()
                    d = body.get("detail")
                    if isinstance(d, str):
                        detail = d
                    elif isinstance(d, list) and d and isinstance(d[0], dict) and "msg" in d[0]:
                        detail = "; ".join(item.get("msg", str(item)) for item in d[:3])
                except Exception:
                    pass
            st.sidebar.error(detail)
        except Exception as e:
            st.sidebar.error(str(e))

# File upload
uploaded_file = st.sidebar.file_uploader(
    "Or upload your own .dta / .sav",
    type=["dta", "sav"],
    help="DHS/EDHS dataset (max 200MB).",
)
# Clear upload error when user picks a new file
if "edhs_upload_error" in st.session_state and (uploaded_file is None or st.session_state.get("edhs_upload_file_name") != (uploaded_file.name if uploaded_file else None)):
    st.session_state.pop("edhs_upload_error", None)
    st.session_state.pop("edhs_upload_file_name", None)

if uploaded_file is not None:
    # Keep file bytes in session so we don't exhaust the stream on retry
    if st.session_state.get("edhs_upload_file_name") != uploaded_file.name:
        st.session_state["edhs_upload_file_bytes"] = uploaded_file.read()
        st.session_state["edhs_upload_file_name"] = uploaded_file.name
    file_bytes = st.session_state.get("edhs_upload_file_bytes") or b""

    st.sidebar.caption(
        f"File: **{uploaded_file.name}** — click **Upload dataset** below to send it to the server and create a session."
    )
    if st.sidebar.button("Upload dataset", type="primary"):
        if not file_bytes:
            st.session_state["edhs_upload_error"] = "The file is empty. Select the file again and retry."
            st.rerun()
        try:
            with st.sidebar.spinner("Uploading…"):
                resp = api_upload(
                    base_url,
                    tenant_id,
                    bearer_token or None,
                    file_bytes,
                    uploaded_file.name,
                    survey_country_code=sidebar_country.strip() or None,
                    survey_year=int(sidebar_year),
                    survey_type=sidebar_type if sidebar_type != "Other" else None,
                )
            st.session_state["edhs_session_id"] = resp["session_id"]
            st.session_state["edhs_session_source"] = "upload"
            st.session_state["edhs_survey_country_code"] = resp.get("survey_country_code")
            st.session_state["edhs_survey_year"] = resp.get("survey_year")
            st.session_state["edhs_survey_type"] = resp.get("survey_type")
            history = st.session_state.setdefault("edhs_sessions_history", [])
            history.append(
                {
                    "session_id": resp["session_id"],
                    "country": resp.get("survey_country_code"),
                    "year": resp.get("survey_year"),
                    "type": resp.get("survey_type"),
                    "filename": resp.get("filename", uploaded_file.name),
                }
            )
            st.session_state.pop("edhs_upload_error", None)
            st.session_state.pop("edhs_upload_file_bytes", None)
            st.session_state.pop("edhs_upload_file_name", None)
            st.sidebar.success(f"Uploaded: `{uploaded_file.name}`")
            st.rerun()
        except requests.HTTPError as e:
            detail = str(e)
            if e.response is not None:
                try:
                    body = e.response.json()
                    d = body.get("detail")
                    if isinstance(d, str):
                        detail = d
                    elif isinstance(d, list) and d and isinstance(d[0], dict) and "msg" in d[0]:
                        detail = "; ".join(item.get("msg", str(item)) for item in d[:3])
                except Exception:
                    pass
            st.session_state["edhs_upload_error"] = detail
            st.rerun()
        except Exception as e:
            st.session_state["edhs_upload_error"] = str(e)
            st.rerun()

if session_id:
    st.sidebar.caption(f"Active session: `{session_id[:16]}…`")
    if st.sidebar.button("Clear session", type="secondary"):
        del st.session_state["edhs_session_id"]
        st.session_state.pop("edhs_session_source", None)
        st.session_state.pop("edhs_survey_country_code", None)
        st.session_state.pop("edhs_survey_year", None)
        st.session_state.pop("edhs_survey_type", None)
        st.session_state.pop("edhs_last_result", None)
        st.session_state.pop("edhs_last_geojson", None)
        st.session_state.pop("edhs_last_grouped", None)
        st.session_state.pop("edhs_upload_error", None)
        # Keep session history for multi-country comparison
        st.rerun()
else:
    st.sidebar.info(
        "Create a session: **Try with sample data**, **Load from URL**, or upload a .dta/.sav file and click **Upload dataset**."
    )

# Main area – header
st.markdown(
    '<div class="edhs-header">'
    '<h1>DHS Hybrid Plugin Platform</h1>'
    '<p>Explore DHS/EDHS data — fetch indicators, visualize trends, and export for research.</p>'
    '</div>',
    unsafe_allow_html=True,
)

# Route main content by navigation
if nav_choice == "🏠 Home":
    st.markdown("### Welcome")
    st.markdown(
        "The **DHS Hybrid Plugin Platform** lets you explore Demographic and Health Survey (DHS) data: "
        "fetch indicators from the DHS Program API, visualize trends, compute from microdata, and export for research."
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Backend", "Connected" if st.session_state.get("edhs_connection_ok") else "Disconnected", "")
    with col2:
        st.metric("Session", "Active" if session_id else "None", "")
    with col3:
        has_dhs = "Yes" if st.session_state.get("edhs_dhs_api_data") else "No"
        st.metric("DHS data loaded", has_dhs, "")
    st.markdown("---")
    st.markdown("#### Quick start")
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        if st.button("📡 Go to DHS Program API", use_container_width=True, key="nav_dhs"):
            st.session_state["edhs_nav_pending"] = "📡 DHS Program API"
            st.rerun()
    with q2:
        if st.button("📂 Go to Microdata Analysis", use_container_width=True, key="nav_micro"):
            st.session_state["edhs_nav_pending"] = "📂 Microdata Analysis"
            st.rerun()
    with q3:
        if st.button("📊 Go to Custom Dashboard", use_container_width=True, key="nav_dash"):
            st.session_state["edhs_nav_pending"] = "📊 Custom Dashboard"
            st.rerun()
    with q4:
        if st.button("⚙️ Go to Settings", use_container_width=True, key="nav_set"):
            st.session_state["edhs_nav_pending"] = "⚙️ Settings"
            st.rerun()
    st.markdown("---")
    st.markdown("**Need data?** Use the sidebar to fetch from the DHS Program API, try sample data, or upload a .dta/.sav file.")
    st.caption("New to the platform? Use **Onboarding** in the sidebar for a step-by-step guide.")
    st.stop()

elif nav_choice == "📖 Onboarding":
    st.markdown("## 📖 Welcome to the DHS Hybrid Plugin Platform")
    st.markdown(
        "This platform helps you explore **Demographic and Health Survey (DHS)** data: "
        "fetch indicators from the DHS Program API, visualize trends, compute from microdata, and export for research."
    )
    st.markdown("---")
    st.markdown("### What you can do")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**📡 DHS Program API**
- Fetch aggregated indicators (fertility, child health, maternal health, etc.)
- No session or microdata required
- Visualize with heatmaps, time series, radar charts, and more
- Export to CSV, Excel, Stata, SPSS
        """)
    with col2:
        st.markdown("""
**📂 Microdata Analysis**
- Upload .dta or .sav files (DHS/EDHS datasets)
- Compute indicators with sampling weights
- Disaggregate by region, residence, education, wealth
- Generate choropleth maps in QGIS

**📊 Custom Dashboard**
- Build a dashboard from DHS API or microdata results
- Add metrics, charts, and tables as widgets
- Arrange and view in one place
        """)
    st.markdown("---")
    st.markdown("### Quick start (3 steps)")
    st.markdown("""
1. **Check connection** — Open the sidebar and ensure the backend URL is correct (`http://127.0.0.1:8000/api/v1`). Click *Check connection*.
2. **Get data** — Use **DHS Program API** to fetch indicators, or **Try with sample data** / upload a file for microdata.
3. **Explore** — View visualizations, export data, and generate citations.
    """)
    st.markdown("---")
    st.markdown("### Get started")
    ob1, ob2, ob3, ob4 = st.columns(4)
    with ob1:
        if st.button("📡 Go to DHS Program API", use_container_width=True, key="onb_nav_dhs"):
            st.session_state["edhs_nav_pending"] = "📡 DHS Program API"
            st.rerun()
    with ob2:
        if st.button("📂 Go to Microdata Analysis", use_container_width=True, key="onb_nav_micro"):
            st.session_state["edhs_nav_pending"] = "📂 Microdata Analysis"
            st.rerun()
    with ob3:
        if st.button("📊 Go to Custom Dashboard", use_container_width=True, key="onb_nav_dash"):
            st.session_state["edhs_nav_pending"] = "📊 Custom Dashboard"
            st.rerun()
    with ob4:
        if st.button("⚙️ Go to Settings", use_container_width=True, key="onb_nav_set"):
            st.session_state["edhs_nav_pending"] = "⚙️ Settings"
            st.rerun()
    st.markdown("---")
    st.caption("Data from [The DHS Program](https://dhsprogram.com). See methodology notes in each section.")
    st.stop()

elif nav_choice == "📡 DHS Program API":
    st.markdown("## 📡 DHS Program API – Indicators & Data")
    st.caption(
        "STATcompiler-style data: your backend performs a single GET to DHS `/data`, maps ISO3→two-letter "
        "country codes, applies optional `breakdown`, then filters by survey year and dedupes the `Data` array. "
        "Configure **Backend base URL** in the sidebar; a DHS key may be set server-side (`DHS_PROGRAM_API_KEY`)."
    )
    auto_fetch = os.environ.get("DHS_AUTO_FETCH", "").strip().lower() in ("1", "true", "yes")
    if (
        auto_fetch
        and st.session_state.get("edhs_dhs_api_data") is None
        and "edhs_dhs_auto_fetch_tried" not in st.session_state
    ):
        st.session_state["edhs_dhs_auto_fetch_tried"] = True
        cc_auto = os.environ.get("DHS_AUTO_COUNTRIES", "SEN,KEN,BEN,GHA")
        ii_auto = os.environ.get("DHS_AUTO_INDICATORS", "FE_FRTR_W_TFR,CM_ECMR_C_IMR")
        y0_auto = int(os.environ.get("DHS_AUTO_YEAR_START", "2000"))
        y1_auto = int(os.environ.get("DHS_AUTO_YEAR_END", "2024"))
        try:
            _require_edhs_backend_base_url(base_url)
            with st.spinner("Loading DHS data (automatic)…"):
                dhs_auto = api_dhs_data_fetch(
                    base_url,
                    tenant_id,
                    bearer_token or None,
                    country_ids=cc_auto,
                    indicator_ids=ii_auto,
                    survey_year_start=y0_auto,
                    survey_year_end=y1_auto,
                    dhs_api_key=dhs_api_key or None,
                )
            st.session_state["edhs_dhs_api_data"] = dhs_auto
            st.session_state["edhs_dhs_fetch_countries"] = cc_auto
            st.session_state["edhs_dhs_fetch_indicators"] = ii_auto
            st.session_state.pop("edhs_dhs_indicators", None)
            st.success(f"Automatically loaded {len(dhs_auto.get('Data', []))} records.")
            st.rerun()
        except Exception as e:
            st.info("Automatic DHS fetch was skipped or failed; use the form below. " + str(e))

    with st.expander("Fetch data (quick)", expanded=True):
        default_iso = ["SEN", "KEN", "BEN", "GHA"]
        sel_iso = st.multiselect(
            "Countries (ISO3)",
            options=_DHS_ISO3_MULTI_OPTIONS,
            default=[c for c in default_iso if c in _DHS_ISO3_MULTI_OPTIONS],
            key="dhs_nav_iso3_multi",
            help="Mapped to DHS two-letter codes before the API call.",
        )
        preset_labels = [p[0] for p in _DHS_QUICK_INDICATOR_PRESETS]
        preset_ids = [p[1] for p in _DHS_QUICK_INDICATOR_PRESETS]
        default_lbl = preset_labels[:2] if len(preset_labels) > 1 else preset_labels[:1]
        sel_lbl = st.multiselect(
            "Indicators",
            options=preset_labels,
            default=default_lbl,
            key="dhs_nav_ind_presets",
            help="Official DHS IndicatorId values (not every indicator is available for every country-year).",
        )
        dhs_breakdown = st.text_input(
            "Breakdown (optional)",
            value="",
            key="dhs_nav_breakdown",
            help="If supported by the DHS API for your indicators, pass a breakdown code here.",
        )
        dhs_year_col1, dhs_year_col2 = st.columns(2)
        with dhs_year_col1:
            dhs_year_start = st.number_input(
                "Survey year from", min_value=1990, max_value=2030, value=2000, key="dhs_yr_start_nav"
            )
        with dhs_year_col2:
            dhs_year_end = st.number_input(
                "Survey year to", min_value=1990, max_value=2030, value=2024, key="dhs_yr_end_nav"
            )
        if st.button("Fetch DHS data", key="dhs_fetch_nav", type="primary"):
            if not sel_iso or not sel_lbl:
                st.error("Select at least one country and one indicator.")
            else:
                id_csv = ",".join(preset_ids[preset_labels.index(lab)] for lab in sel_lbl)
                c_csv = ",".join(sel_iso)
                try:
                    with st.spinner("Fetching…"):
                        dhs_resp = api_dhs_data_fetch(
                            base_url,
                            tenant_id,
                            bearer_token or None,
                            country_ids=c_csv,
                            indicator_ids=id_csv,
                            survey_year_start=int(dhs_year_start),
                            survey_year_end=int(dhs_year_end),
                            dhs_api_key=dhs_api_key or None,
                            breakdown=dhs_breakdown.strip() or None,
                        )
                    st.session_state["edhs_dhs_api_data"] = dhs_resp
                    st.session_state["edhs_dhs_fetch_countries"] = c_csv
                    st.session_state["edhs_dhs_fetch_indicators"] = id_csv
                    st.session_state.pop("edhs_dhs_indicators", None)
                    st.success(f"Retrieved {len(dhs_resp.get('Data', []))} records.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        if _DHS_RESEARCH_AVAILABLE and (SUGGESTED_BY_TOPIC or COMPARISON_TEMPLATES):
            with st.expander("💡 Suggested indicators & templates", expanded=False):
                for topic, inds in list(SUGGESTED_BY_TOPIC.items())[:3]:
                    if st.button(
                        f"Use {topic}: " + ",".join(inds[:2]) + "…",
                        key=f"dhs_nav_sug_{hash(topic) % 10**8}",
                    ):
                        st.session_state["edhs_dhs_fetch_indicators"] = ",".join(inds)
                        st.rerun()
                for idx, (label, c, i) in enumerate(COMPARISON_TEMPLATES[:3]):
                    if st.button(f"Template: {label}", key=f"dhs_nav_tpl_{idx}"):
                        st.session_state["edhs_dhs_fetch_countries"] = c
                        st.session_state["edhs_dhs_fetch_indicators"] = i
                        st.rerun()
        with st.expander("Advanced: typed country & indicator codes (ISO3 or DHS alpha-2)", expanded=False):
            dhs_country_input = st.text_input(
                "Country codes (comma-separated)",
                value=st.session_state.get("edhs_dhs_fetch_countries", "BJ"),
                key="dhs_countries_nav",
            )
            dhs_indicator_input = st.text_input(
                "Indicator IDs (comma-separated)",
                value=st.session_state.get("edhs_dhs_fetch_indicators", "FE_FRTR_W_A15,CN_ANMC_C_ANY"),
                key="dhs_indicators_nav",
            )
            if st.button("Fetch with typed codes", key="dhs_fetch_typed_nav"):
                if dhs_country_input.strip() and dhs_indicator_input.strip():
                    try:
                        with st.spinner("Fetching…"):
                            dhs_resp = api_dhs_data_fetch(
                                base_url,
                                tenant_id,
                                bearer_token or None,
                                country_ids=dhs_country_input.strip(),
                                indicator_ids=dhs_indicator_input.strip(),
                                survey_year_start=int(dhs_year_start),
                                survey_year_end=int(dhs_year_end),
                                dhs_api_key=dhs_api_key or None,
                                breakdown=dhs_breakdown.strip() or None,
                            )
                        st.session_state["edhs_dhs_api_data"] = dhs_resp
                        st.session_state["edhs_dhs_fetch_countries"] = dhs_country_input.strip()
                        st.session_state["edhs_dhs_fetch_indicators"] = dhs_indicator_input.strip()
                        st.session_state.pop("edhs_dhs_indicators", None)
                        st.success(f"Retrieved {len(dhs_resp.get('Data', []))} records.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.error("Enter country codes and indicator IDs.")
    if st.session_state.get("edhs_dhs_api_data"):
        _render_dhs_research_ui(st.session_state["edhs_dhs_api_data"], st.session_state.get("edhs_dhs_fetch_countries", "BJ"), st.session_state.get("edhs_dhs_fetch_indicators", ""), int(st.session_state.get("dhs_yr_start_nav", 2000)), int(st.session_state.get("dhs_yr_end_nav", 2024)), key_prefix="dhs_nav")
        st.download_button("Export JSON", data=json.dumps(st.session_state["edhs_dhs_api_data"], indent=2).encode("utf-8"), file_name="dhs_export.json", mime="application/json", key="dhs_json_nav")
    with st.expander("Browse indicators catalog", expanded=False):
        if st.button("Load catalog", key="dhs_catalog_nav"):
            try:
                ind_resp = api_dhs_indicators(base_url, tenant_id, bearer_token or None, per_page=50, dhs_api_key=dhs_api_key or None)
                st.session_state["edhs_dhs_indicators"] = ind_resp
                st.rerun()
            except Exception as e:
                st.error(str(e))
        if st.session_state.get("edhs_dhs_indicators"):
            ind_list = st.session_state["edhs_dhs_indicators"].get("Data", [])
            if ind_list:
                sample_df = pd.DataFrame(ind_list[:50])
                cols = [c for c in ["IndicatorId", "ShortName", "Label"] if c in sample_df.columns]
                if cols:
                    st.dataframe(sample_df[cols], use_container_width=True)
    st.stop()

elif nav_choice == "📋 DHS Indicators":
    st.markdown("## 📋 DHS Indicators Reference")
    st.caption(
        "Common DHS Program API indicators with example API calls. "
        "Use these Indicator IDs in the **DHS Program API** section to fetch data."
    )
    indicators_data = [
        (1, "FE_FRTR_W_TFR", "Total fertility rate (average number of children per woman)", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=FE_FRTR_W_TFR&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (2, "CM_ECMR_C_IMR", "Infant mortality rate (deaths before age 1)", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=CM_ECMR_C_IMR&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (3, "CM_ECMR_C_U5M", "Under-five mortality rate", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=CM_ECMR_C_U5M&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (4, "RH_ANCN_W_ANY", "Women receiving antenatal care (at least one visit)", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=RH_ANCN_W_ANY&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (5, "RH_DEL_W_INST", "Births delivered in a health facility", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=RH_DEL_W_INST&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (6, "RH_DEL_W_SBA", "Births assisted by skilled health personnel", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=RH_DEL_W_SBA&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (7, "FP_CUSE_W_ANY", "Women using any contraceptive method", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=FP_CUSE_W_ANY&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (8, "FP_CUSE_W_MOD", "Women using modern contraceptive methods", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=FP_CUSE_W_MOD&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (9, "FP_UNMN_W_ANY", "Unmet need for family planning", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=FP_UNMN_W_ANY&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (10, "CH_VACC_C_BCG", "Children receiving BCG vaccination", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=CH_VACC_C_BCG&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (11, "CH_VACC_C_DPT3", "Children receiving 3 doses of DPT vaccine", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=CH_VACC_C_DPT3&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (12, "CH_VACC_C_MEAS", "Children vaccinated against measles", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=CH_VACC_C_MEAS&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (13, "CH_DIAR_C_ORS", "Children with diarrhea treated with ORS", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=CH_DIAR_C_ORS&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (14, "NT_STNT_C_HA2", "Children under 5 who are stunted", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=NT_STNT_C_HA2&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (15, "NT_WAST_C_WH2", "Children under 5 who are wasted", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=NT_WAST_C_WH2&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (16, "NT_UNDW_C_WA2", "Children under 5 who are underweight", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=NT_UNDW_C_WA2&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (17, "ML_NETS_H_OWN", "Households owning at least one mosquito net", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=ML_NETS_H_OWN&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (18, "ML_FEVT_C_ADV", "Children with fever for whom advice or treatment was sought", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=ML_FEVT_C_ADV&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (19, "ML_PMAL_C_RDT", "Malaria prevalence (rapid diagnostic test)", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=ML_PMAL_C_RDT&countryIds=SN&f=json&apiKey=SPEROF-176817"),
        (20, "HV_HIVP_A_PRE", "HIV prevalence among adults", "https://api.dhsprogram.com/rest/dhs/data?indicatorIds=HV_HIVP_A_PRE&countryIds=SN&f=json&apiKey=SPEROF-176817"),
    ]
    df_indicators = pd.DataFrame(
        indicators_data,
        columns=["#", "Indicator ID", "Description", "Example API Call"],
    )
    st.dataframe(
        df_indicators,
        use_container_width=True,
        column_config={
            "Example API Call": st.column_config.LinkColumn("Example API Call", display_text="Open URL"),
        },
        hide_index=True,
    )
    st.caption("Data from [The DHS Program API](https://api.dhsprogram.com). Replace countryIds and apiKey in URLs as needed.")
    if st.button("📡 Go to DHS Program API", key="ind_ref_to_dhs"):
        st.session_state["edhs_nav_pending"] = "📡 DHS Program API"
        st.rerun()
    st.stop()

elif nav_choice == "📊 Custom Dashboard":
    st.markdown("## 📊 Custom Dashboard")
    st.caption(
        "Build a custom dashboard by adding widgets from your DHS API data or microdata results. "
        "Widgets are saved for this session."
    )

    # Initialize dashboard state
    if "edhs_dashboard_widgets" not in st.session_state:
        st.session_state["edhs_dashboard_widgets"] = []

    widgets = st.session_state["edhs_dashboard_widgets"]

    # --- Builder ---
    with st.expander("➕ Add widget", expanded=len(widgets) == 0):
        data_sources: List[tuple] = []
        if st.session_state.get("edhs_dhs_api_data"):
            data_sources.append(("DHS Program API data", "dhs_api"))
        if st.session_state.get("edhs_last_result"):
            data_sources.append(("Microdata indicator (last result)", "microdata_indicator"))
        if st.session_state.get("edhs_last_grouped"):
            data_sources.append(("Microdata disaggregated (by group)", "microdata_grouped"))
        if st.session_state.get("edhs_last_multi"):
            data_sources.append(("Microdata multiple indicators", "microdata_multi"))

        if not data_sources:
            st.info("Load data first: fetch from **DHS Program API** or compute indicators in **Microdata Analysis**.")
        else:
            ds_label = st.selectbox(
                "Data source",
                options=[x[0] for x in data_sources],
                key="dash_add_ds",
            )
            ds_key = next(k for lbl, k in data_sources if lbl == ds_label)

            add_col1, add_col2, add_col3 = st.columns(3)
            with add_col1:
                widget_type = st.selectbox(
                    "Widget type",
                    ["Metric", "Bar chart", "Table", "Gauge"],
                    key="dash_add_type",
                )
            # Build metric/indicator options based on data source AND widget type
            metric_options: List[tuple] = []  # (label, key)
            if ds_key == "dhs_api":
                dhs_data = st.session_state["edhs_dhs_api_data"]
                df_ds = get_dhs_dataframe(dhs_data) if _DHS_RESEARCH_AVAILABLE else pd.DataFrame(dhs_data.get("Data", []))
                if not df_ds.empty and "Value" in df_ds.columns:
                    ind_col = "IndicatorId" if "IndicatorId" in df_ds.columns else "Indicator"
                    ctry_col = "CountryName" if "CountryName" in df_ds.columns else None
                    yr_col = "SurveyYear" if "SurveyYear" in df_ds.columns else None
                    # Single-value options for Metric/Gauge/Table
                    single_opts: List[tuple] = []
                    for _, row in df_ds.iterrows():
                        ind = str(row.get(ind_col, ""))
                        ctry = str(row.get(ctry_col, "")) if ctry_col else ""
                        yr = str(int(row.get(yr_col, ""))) if yr_col and pd.notna(row.get(yr_col)) else ""
                        parts = [ind, ctry, yr]
                        label = " | ".join(p for p in parts if p)
                        key = f"{ind}||{ctry}||{yr}"
                        if (label, key) not in single_opts:
                            single_opts.append((label, key))
                    # Bar options for Bar chart
                    bar_opts: List[tuple] = []
                    for ind in df_ds[ind_col].unique()[:20]:
                        bar_opts.append((f"{ind} (by country)", f"bar_country||{ind}"))
                        bar_opts.append((f"{ind} (by year)", f"bar_year||{ind}"))
                    # Show coherent options per widget type
                    if widget_type == "Bar chart":
                        metric_options = bar_opts
                    else:
                        metric_options = single_opts
            elif ds_key == "microdata_multi":
                rows = st.session_state["edhs_last_multi"]
                for i, r in enumerate(rows):
                    name = r.get("name", r.get("indicator_id", f"Indicator {i}"))
                    metric_options.append((name, r.get("indicator_id", str(i))))
            elif ds_key == "microdata_grouped":
                metric_options = [
                    ("Estimate by group", "estimate"),
                    ("Population N by group", "population_n"),
                ]
            elif ds_key == "microdata_indicator":
                metric_options = [("Last computed value", "value")]

            with add_col2:
                metric_label = ""
                if metric_options:
                    metric_label = st.selectbox(
                        "Metric / indicator",
                        options=[x[0] for x in metric_options],
                        key="dash_add_metric",
                        help="Choose which metric or indicator to display.",
                    )
                    metric_key = next(k for lbl, k in metric_options if lbl == metric_label)
                else:
                    metric_key = ""
            with add_col3:
                widget_title = st.text_input("Title (optional)", placeholder="e.g. Contraception rate", key="dash_add_title")

            if st.button("Add widget", type="primary", key="dash_add_btn"):
                import uuid
                display_title = widget_title or (metric_label if metric_options else f"Widget {len(widgets) + 1}")
                widgets.append({
                    "id": str(uuid.uuid4())[:8],
                    "data_source": ds_key,
                    "widget_type": widget_type.lower().replace(" ", "_"),
                    "title": display_title,
                    "metric_key": metric_key if metric_options else "",
                })
                st.rerun()

    # --- Remove widget (check session state for pending removal) ---
    if "edhs_dash_remove_id" in st.session_state:
        rid = st.session_state.pop("edhs_dash_remove_id")
        st.session_state["edhs_dashboard_widgets"] = [x for x in widgets if x["id"] != rid]
        st.rerun()

    # --- Remove widget ---
    if widgets:
        st.markdown("---")
        st.markdown("### Dashboard")
        for w in widgets:
            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.caption(f"**{w['title']}** — {w['widget_type']} from {w['data_source']}")
            with col_b:
                if st.button("🗑 Remove", key=f"dash_rm_{w['id']}"):
                    st.session_state["edhs_dash_remove_id"] = w["id"]
                    st.rerun()

        # --- Render widgets in grid ---
        st.markdown("---")
        cols = st.columns(min(3, len(widgets)))
        for i, w in enumerate(widgets):
            with cols[i % 3]:
                try:
                    metric_key = w.get("metric_key", "")

                    if w["data_source"] == "dhs_api":
                        dhs_data = st.session_state["edhs_dhs_api_data"]
                        df_full = get_dhs_dataframe(dhs_data) if _DHS_RESEARCH_AVAILABLE else pd.DataFrame(dhs_data.get("Data", []))
                        # Filter by selected metric/indicator
                        if metric_key.startswith("bar_country||"):
                            ind_id = metric_key.split("||", 1)[1]
                            ind_col = "IndicatorId" if "IndicatorId" in df_full.columns else "Indicator"
                            df = df_full[df_full[ind_col] == ind_id].copy() if ind_col in df_full.columns else df_full
                            if "CountryName" in df.columns:
                                df = df.groupby("CountryName", as_index=False).agg({"Value": "mean"})
                                df = df.rename(columns={"CountryName": "group_value", "Value": "estimate"})
                        elif metric_key.startswith("bar_year||"):
                            ind_id = metric_key.split("||", 1)[1]
                            ind_col = "IndicatorId" if "IndicatorId" in df_full.columns else "Indicator"
                            df = df_full[df_full[ind_col] == ind_id].copy() if ind_col in df_full.columns else df_full
                            if "SurveyYear" in df.columns:
                                df = df.groupby("SurveyYear", as_index=False).agg({"Value": "mean"})
                                df = df.rename(columns={"SurveyYear": "group_value", "Value": "estimate"})
                        elif "||" in metric_key:
                            parts = metric_key.split("||")
                            ind_col = "IndicatorId" if "IndicatorId" in df_full.columns else "Indicator"
                            mask = df_full[ind_col] == parts[0] if ind_col in df_full.columns else pd.Series([True] * len(df_full))
                            if len(parts) > 1 and parts[1] and "CountryName" in df_full.columns:
                                mask = mask & (df_full["CountryName"] == parts[1])
                            if len(parts) > 2 and parts[2] and "SurveyYear" in df_full.columns:
                                mask = mask & (df_full["SurveyYear"].astype(str) == parts[2])
                            df = df_full[mask].head(1)
                        else:
                            df = df_full
                    elif w["data_source"] == "microdata_indicator":
                        res = st.session_state["edhs_last_result"]
                        df = pd.DataFrame([{"value": res.get("value"), "name": res.get("metadata", {}).get("name", "Value")}])
                    elif w["data_source"] == "microdata_grouped":
                        gr = st.session_state["edhs_last_grouped"]
                        df = pd.DataFrame(gr.get("rows", []))
                        if metric_key == "population_n" and "population_n" in df.columns:
                            df = df[["group_value", "population_n"]].rename(columns={"population_n": "estimate"})
                    elif w["data_source"] == "microdata_multi":
                        rows = st.session_state["edhs_last_multi"]
                        if metric_key:
                            rows = [r for r in rows if r.get("indicator_id") == metric_key]
                        df = pd.DataFrame(rows) if rows else pd.DataFrame()
                    else:
                        df = pd.DataFrame()

                    if df.empty:
                        st.warning(f"No data for {w['title']}")
                        continue

                    st.markdown(f"**{w['title']}**")
                    if w["widget_type"] == "metric":
                        if "value" in df.columns:
                            v = df["value"].iloc[0] if len(df) > 0 else 0
                            st.metric(w["title"], _format_indicator_value(v), "")
                        elif "Value" in df.columns:
                            v = df["Value"].iloc[0] if len(df) > 0 else 0
                            st.metric(w["title"], _format_indicator_value(v), "")
                        elif "estimate" in df.columns:
                            v = df["estimate"].iloc[0] if len(df) > 0 else 0
                            st.metric(w["title"], _format_indicator_value(v), "")
                        else:
                            st.metric(w["title"], str(df.iloc[0, 0]), "")
                    elif w["widget_type"] == "bar_chart":
                        # Bar chart needs multiple rows; if single-row (wrong option), show as metric
                        if len(df) < 2 and "Value" in df.columns:
                            v = df["Value"].iloc[0] if len(df) > 0 else 0
                            st.metric(w["title"], _format_indicator_value(v), "")
                        else:
                            x_col = "group_value" if "group_value" in df.columns else (df.columns[0] if len(df.columns) > 0 else None)
                            y_col = "estimate" if "estimate" in df.columns else ("Value" if "Value" in df.columns else ("value" if "value" in df.columns else (df.columns[1] if len(df.columns) > 1 else None)))
                            if x_col and y_col:
                                try:
                                    import plotly.graph_objects as go
                                    fig = go.Figure(data=[go.Bar(x=df[x_col].astype(str), y=df[y_col], marker_color="#0d9488")])
                                    fig.update_layout(margin=dict(l=20, r=20, t=30, b=40), height=220)
                                    st.plotly_chart(fig, use_container_width=True, key=f"dash_bar_{w['id']}")
                                except Exception:
                                    st.dataframe(df.head(10), use_container_width=True)
                            else:
                                st.dataframe(df.head(10), use_container_width=True)
                    elif w["widget_type"] == "gauge":
                        v = df["value"].iloc[0] if "value" in df.columns and len(df) > 0 else (df["Value"].iloc[0] if "Value" in df.columns and len(df) > 0 else (df["estimate"].iloc[0] if "estimate" in df.columns and len(df) > 0 else 0))
                        v = float(v) if isinstance(v, (int, float)) else 0
                        try:
                            # Gauge: use 0-100 for percentages, else scale
                            max_val = 100 if v <= 100 else max(100, v * 1.2)
                            fig_g = chart_gauge(v, w["title"], min_val=0, max_val=max_val) if _DHS_RESEARCH_AVAILABLE else None
                            if fig_g:
                                st.plotly_chart(fig_g, use_container_width=True, key=f"dash_gauge_{w['id']}")
                            else:
                                st.metric(w["title"], _format_indicator_value(v), "")
                        except Exception:
                            st.metric(w["title"], _format_indicator_value(v), "")
                    else:
                        st.dataframe(df.head(15), use_container_width=True)
                except Exception as e:
                    st.error(f"Error rendering {w['title']}: {e}")

        if st.button("Clear all widgets", key="dash_clear"):
            st.session_state["edhs_dashboard_widgets"] = []
            st.rerun()
    else:
        st.info("Add widgets above to build your dashboard. Load data from DHS Program API or Microdata Analysis first.")
    st.stop()

elif nav_choice == "⚙️ Settings":
    st.markdown("## ⚙️ Settings")
    st.markdown("Connection and API configuration.")
    with st.form("settings_form"):
        base_url_set = st.text_input("API base URL", value=base_url, key="settings_base_url")
        tenant_id_set = st.text_input("Tenant ID", value=tenant_id, key="settings_tenant")
        bearer_set = st.text_input("JWT token (optional)", type="password", value=bearer_token or "", key="settings_bearer")
        if st.form_submit_button("Save (reload to apply)"):
            st.info("Change the values in the sidebar 'Backend connection' expander and rerun. Session state is not persisted.")
    if st.button("Check connection"):
        ok = api_health(base_url, tenant_id, bearer_token or None, dhs_api_key or None)
        if ok:
            st.success("Backend is reachable.")
        else:
            st.error("Cannot reach backend.")
    st.stop()

elif nav_choice == "📂 Microdata Analysis":
    if not st.session_state.get("edhs_session_id"):
        st.info("👈 **Open the sidebar** to create a session: **Try with sample data**, **Load from URL**, or upload a .dta/.sav file.")
        if st.session_state.get("edhs_upload_error"):
            st.error("**Upload error:** " + st.session_state["edhs_upload_error"])
            st.caption(
                "Use the sidebar to reselect a file or try sample data below."
            )
            if st.button("Try with sample data", type="primary", key="sample_after_error"):
                try:
                    resp = api_mock_session(
                        base_url, tenant_id, bearer_token or None,
                        survey_country_code=(st.session_state.get("sidebar_country") or "ETH").strip() or None,
                        survey_year=int(st.session_state.get("sidebar_year", 2019)),
                        survey_type=st.session_state.get("sidebar_type") or "DHS",
                    )
                    st.session_state["edhs_session_id"] = resp["session_id"]
                    st.session_state["edhs_session_source"] = "sample"
                    st.session_state["edhs_survey_country_code"] = resp.get("survey_country_code")
                    st.session_state["edhs_survey_year"] = resp.get("survey_year")
                    st.session_state["edhs_survey_type"] = resp.get("survey_type")
                    history = st.session_state.setdefault("edhs_sessions_history", [])
                    history.append({"session_id": resp["session_id"], "country": resp.get("survey_country_code"), "year": resp.get("survey_year"), "type": resp.get("survey_type"), "filename": resp.get("filename", "sample")})
                    st.session_state.pop("edhs_upload_error", None)
                    st.success("Session created.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        st.markdown("---")

if nav_choice == "📂 Microdata Analysis" and not session_id:
    st.markdown("---")
    # If a file is already selected in the sidebar, offer to send it from the main area
    upload_name = st.session_state.get("edhs_upload_file_name")
    upload_bytes = st.session_state.get("edhs_upload_file_bytes")
    if upload_name and upload_bytes:
        st.info(f"**Selected file:** {upload_name} — send it to the server to create the session.")
        if st.button("Send file and create session", type="primary", key="upload_from_main"):
            try:
                st.info("Uploading file (large files may take 1–2 minutes)…")
                st.warning("Do not close this page.")
                with st.spinner("Uploading…"):
                    resp = api_upload(
                        base_url,
                        tenant_id,
                        bearer_token or None,
                        upload_bytes,
                        upload_name,
                        survey_country_code=(st.session_state.get("sidebar_country") or "ETH").strip() or None,
                        survey_year=int(st.session_state.get("sidebar_year", 2019)),
                        survey_type=st.session_state.get("sidebar_type") or "DHS",
                    )
                st.session_state["edhs_session_id"] = resp["session_id"]
                st.session_state["edhs_session_source"] = "upload"
                st.session_state["edhs_survey_country_code"] = resp.get("survey_country_code")
                st.session_state["edhs_survey_year"] = resp.get("survey_year")
                st.session_state["edhs_survey_type"] = resp.get("survey_type")
                st.session_state.pop("edhs_upload_error", None)
                st.session_state.pop("edhs_upload_file_bytes", None)
                st.session_state.pop("edhs_upload_file_name", None)
                st.success("Session created. You can now select an indicator.")
                st.rerun()
            except requests.HTTPError as e:
                detail = str(e)
                if e.response is not None:
                    try:
                        body = e.response.json()
                        d = body.get("detail")
                        if isinstance(d, str):
                            detail = d
                        elif isinstance(d, list) and d and isinstance(d[0], dict) and "msg" in d[0]:
                            detail = "; ".join(item.get("msg", str(item)) for item in d[:3])
                    except Exception:
                        pass
                st.session_state["edhs_upload_error"] = detail
                st.rerun()
            except Exception as e:
                st.session_state["edhs_upload_error"] = str(e)
                st.rerun()
    st.markdown("---")
    # Friendly empty state with steps and CTA
    st.markdown("### Getting started")
    st.markdown(
        "**First:** start the backend (e.g. `uvicorn edhs_core.main:app --reload`) and set **Backend base URL** in the sidebar to your API root (e.g. `http://127.0.0.1:8000/api/v1`)."
    )
    st.markdown(
        "1. **Check the connection** (sidebar on the left) — the API URL must be correct.  \n"
        "2. **Create a session** — in the sidebar: **Try with sample data**, **Load from URL** (direct .dta/.sav/.zip link), or upload a .dta/.sav file then **Upload dataset**.  \n"
        "3. **Pick an indicator** then run **Compute** or **Compute & show map**."
    )
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Optional survey metadata for first-time try
        c1, c2, c3 = st.columns(3)
        with c1:
            main_country = st.text_input("Country (ISO)", value="ETH", key="main_country", max_chars=3)
        with c2:
            main_year = st.number_input("Year", min_value=1990, max_value=2030, value=2019, step=1, key="main_year")
        with c3:
            main_type = st.selectbox("Survey type", ["DHS", "MIS", "AIS"], key="main_type")
        if st.button("Try with sample data", type="primary", use_container_width=True):
            try:
                resp = api_mock_session(
                    base_url, tenant_id, bearer_token or None,
                    survey_country_code=main_country.strip() or None,
                    survey_year=int(main_year),
                    survey_type=main_type,
                )
                st.session_state["edhs_session_id"] = resp["session_id"]
                st.session_state["edhs_session_source"] = "sample"
                st.session_state["edhs_survey_country_code"] = resp.get("survey_country_code")
                st.session_state["edhs_survey_year"] = resp.get("survey_year")
                st.session_state["edhs_survey_type"] = resp.get("survey_type")
                st.success("Session created. You can now select an indicator and compute.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not create session: {e}")

    st.caption("For DHS Program API data (no session required), use the **DHS Program API** menu.")
    if st.button("Go to DHS Program API", key="go_dhs_nav"):
        st.session_state["edhs_nav_pending"] = "📡 DHS Program API"
        st.rerun()
    st.stop()

# Load indicators once
if "edhs_indicators" not in st.session_state:
    try:
        st.session_state["edhs_indicators"] = api_list_indicators(
            base_url, tenant_id, bearer_token or None
        )
    except Exception as e:
        st.error(
            "**Could not load indicators.** Check that the backend is running and the sidebar API URL is correct, then try again."
        )
        st.caption(str(e))
        if st.button("Retry", key="retry_indicators"):
            st.session_state.pop("edhs_indicators", None)
            st.rerun()
        if st.button("Clear session and start over", key="clear_after_indicator_fail"):
            st.session_state.pop("edhs_session_id", None)
            st.session_state.pop("edhs_indicators", None)
            st.session_state.pop("edhs_survey_country_code", None)
            st.session_state.pop("edhs_survey_year", None)
            st.session_state.pop("edhs_survey_type", None)
            st.rerun()
        st.stop()

indicators = st.session_state["edhs_indicators"]
if not indicators:
    st.warning("No indicators available. Check the backend.")
    if st.button("Retry", key="retry_indicators2"):
        st.session_state.pop("edhs_indicators", None)
        st.rerun()
    st.stop()

# Session active banner (with survey metadata and source)
survey_country = st.session_state.get("edhs_survey_country_code")
survey_year = st.session_state.get("edhs_survey_year")
survey_type = st.session_state.get("edhs_survey_type")
session_source = st.session_state.get("edhs_session_source", "")
source_label = ""
if session_source == "url":
    source_label = " (data from URL)"
elif session_source == "sample":
    source_label = " (sample data)"
elif session_source == "upload":
    source_label = " (uploaded file)"
if survey_country or survey_year or survey_type:
    parts = []
    if survey_country:
        country_label = "Ethiopia" if survey_country.upper() == "ETH" else survey_country.upper()
        parts.append(country_label)
    if survey_type:
        parts.append(survey_type)
    if survey_year:
        parts.append(str(survey_year))
    label = " ".join(parts) + source_label
    st.success(
        f"**Active session: {label}** — 1) Choose an indicator, 2) optionally adjust advanced options, 3) run **Compute** or **Compute & show map**."
    )
else:
    st.success(
        f"**Active session**{source_label} — 1) Choose an indicator, 2) optionally adjust advanced options, 3) run **Compute** or **Compute & show map**."
    )

fetch_countries_meta = st.session_state.get("edhs_dhs_fetch_countries")
if fetch_countries_meta and survey_country:
    _f_iso = _first_iso_from_dhs_fetch_csv(str(fetch_countries_meta))
    _s_iso = str(survey_country).strip().upper()[:3]
    if _f_iso and _s_iso and _f_iso != _s_iso:
        st.warning(
            f"**Data alignment:** DHS Program API data in this browser session targets **{_f_iso}**, "
            f"but this microdata file is labeled **{_s_iso}**. Compare API aggregates to microdata outputs "
            "only when both describe the **same survey / country**."
        )

st.markdown("### 2. Choose the indicator and geographic level")
st.caption(
    "**Country** and **indicator** defaults follow your microdata session when present; otherwise they "
    "follow the last **DHS Program API** fetch (country list and indicator IDs) so the same research slice "
    "carries into analysis."
)

ind_options = {f"{i['id']} – {i['name']}": i["id"] for i in indicators}
_labels = list(ind_options.keys())
_micro_sync_sig = (
    st.session_state.get("edhs_session_id"),
    st.session_state.get("edhs_dhs_fetch_countries"),
    st.session_state.get("edhs_dhs_fetch_indicators"),
    st.session_state.get("edhs_survey_country_code"),
)
if st.session_state.get("_edhs_micro_sync_sig") != _micro_sync_sig:
    st.session_state["_edhs_micro_sync_sig"] = _micro_sync_sig
    st.session_state["edhs_micro_country_iso"] = _microdata_country_default_from_state()
    _pref = _first_micro_indicator_from_dhs_fetch(st.session_state.get("edhs_dhs_fetch_indicators"))
    if _pref and _labels:
        for _lbl in _labels:
            if ind_options[_lbl] == _pref:
                st.session_state["edhs_micro_indicator_select"] = _lbl
                break
        else:
            st.session_state["edhs_micro_indicator_select"] = _labels[0]
    elif "edhs_micro_indicator_select" not in st.session_state and _labels:
        st.session_state["edhs_micro_indicator_select"] = _labels[0]

if "edhs_micro_country_iso" not in st.session_state:
    st.session_state["edhs_micro_country_iso"] = _microdata_country_default_from_state()
if "edhs_micro_indicator_select" not in st.session_state and _labels:
    st.session_state["edhs_micro_indicator_select"] = _labels[0]
if st.session_state.get("edhs_micro_indicator_select") not in ind_options and _labels:
    st.session_state["edhs_micro_indicator_select"] = _labels[0]

col1, col2 = st.columns([2, 1])

with col1:
    ind_label = st.selectbox("Indicator", _labels, key="edhs_micro_indicator_select")
    indicator_id = ind_options[ind_label]

with col2:
    country_code = st.text_input("Country (ISO)", key="edhs_micro_country_iso", max_chars=3)
    admin_level = st.number_input("Admin level", min_value=0, max_value=5, value=1)

# Advanced options (weights and admin columns)
with st.expander("Advanced options (DHS weights and admin unit columns)", expanded=False):
    st.caption("Most of the time you can keep the default values.")
    col_a, col_b = st.columns(2)
    with col_a:
        use_weights = st.checkbox("Use DHS weights", value=True)
        weight_var = st.text_input("Weight var", value="v005")
    with col_b:
        micro_admin = st.text_input("Microdata admin column", value="admin1_code")
        boundary_admin = st.text_input("Boundary admin column", value="admin_id")

st.markdown("### 3. Disaggregate and compute the indicator")

# Disaggregation
st.subheader("Disaggregation")
disagg_options = {
    "None": None,
    "Residence (v025)": "v025",
    "Region (admin1_code)": "admin1_code",
    "Education (v106)": "v106",
    "Wealth quintile (v190)": "v190",
    "Other": "other",
}
disagg_choice = st.selectbox("Disaggregate by", list(disagg_options.keys()))
group_by_column: Optional[str] = None
if disagg_options[disagg_choice] == "other":
    group_by_column = st.text_input("Column name for grouping", placeholder="e.g. v024")
elif disagg_options[disagg_choice]:
    group_by_column = disagg_options[disagg_choice]

if group_by_column and st.button("Compute disaggregated"):
    try:
        grouped = api_compute_grouped(
            base_url,
            tenant_id,
            bearer_token or None,
            session_id,
            indicator_id,
            group_by_column,
            use_weights,
            weight_var,
        )
        st.session_state["edhs_last_grouped"] = grouped
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            detail = "Session not found or expired."
            try:
                body = e.response.json()
                detail = body.get("detail", detail)
            except Exception:
                pass
            st.error(f"{detail} Create a new session from the sidebar (**Try with sample data** or upload a file).")
        else:
            st.error(str(e))
    except Exception as e:
        st.error(str(e))

st.divider()

_choropleth_hidden = _hide_choropleth_ui()
if not _choropleth_hidden:
    _boundaries_root = os.environ.get("ADMIN_BOUNDARIES_ROOT", "/opt/edhs/admin_boundaries")
    st.caption(
        f"**Choropleth** needs admin boundary GeoPackages on the API server: "
        f"`{_boundaries_root}/{{ISO3}}/ADM{{level}}.gpkg`. If that file is missing, you get 404 — "
        "the error message below now includes the API’s **Server detail** line."
    )

cols_btn = st.columns(2 if _choropleth_hidden else 3)

# Compute scalar indicator (single)
with cols_btn[0]:
    if st.button("Compute indicator (single value)"):
        try:
            result = api_compute_indicator(
                base_url,
                tenant_id,
                bearer_token or None,
                session_id,
                indicator_id,
                use_weights,
                weight_var,
            )
            st.session_state["edhs_last_result"] = result
            st.session_state["edhs_last_geojson"] = None
        except Exception as e:
            st.error(str(e))

# Compute multiple indicators into a table
with cols_btn[1]:
    # By default the current indicator is selected; add more as needed.
    multi_labels = list(ind_options.keys())
    default_multi = [ind_label]
    selected_multi = st.multiselect(
        "Multiple indicators (table)",
        options=multi_labels,
        default=default_multi,
        help="Select one or more indicators to compute and show in a table.",
    )
    if st.button("Compute multiple indicators (table)"):
        rows_multi = []
        for lbl in selected_multi:
            ind_id = ind_options[lbl]
            try:
                res = api_compute_indicator(
                    base_url,
                    tenant_id,
                    bearer_token or None,
                    session_id,
                    ind_id,
                    use_weights,
                    weight_var,
                )
                meta = res.get("metadata", {}) or {}
                ci = res.get("ci")
                rows_multi.append(
                    {
                        "indicator_id": res.get("indicator_id", ind_id),
                        "name": meta.get("name", ind_id),
                        "description": meta.get("description", ""),
                        "value": res.get("value"),
                        "ci_lower": ci.get("lower") if ci else None,
                        "ci_upper": ci.get("upper") if ci else None,
                        "population_n": res.get("population_n"),
                        "population_weighted_n": res.get("population_weighted_n"),
                    }
                )
            except Exception as e:
                st.error(f"Error for {lbl}: {e}")
        if rows_multi:
            st.session_state["edhs_last_multi"] = rows_multi

# Compute spatial and show map (optional; off when boundary data is not deployed)
if not _choropleth_hidden:
    with cols_btn[2]:
        if st.button("Compute & show map (choropleth)"):
            try:
                resp = api_spatial_aggregate(
                    base_url,
                    tenant_id,
                    bearer_token or None,
                    session_id,
                    indicator_id,
                    country_code,
                    admin_level,
                    micro_admin,
                    boundary_admin,
                    use_weights,
                    weight_var,
                )
                st.session_state["edhs_last_geojson"] = resp["geojson"]
                st.session_state["edhs_last_spatial_response"] = resp
                st.session_state["edhs_last_result"] = None
            except Exception as e:
                st.error(str(e))

# Display last scalar result
if st.session_state.get("edhs_last_result"):
    res = st.session_state["edhs_last_result"]
    st.subheader("Indicator result")
    v = res.get("value")
    ci = res.get("ci")
    st.metric(
        label=res.get("metadata", {}).get("name", "Value"),
        value=f"{v:.4f}" if isinstance(v, (int, float)) else str(v),
        delta=f"95% CI: [{ci['lower']:.3f}, {ci['upper']:.3f}]" if ci else None,
    )
    if isinstance(v, (int, float)) and ci:
        try:
            import plotly.graph_objects as go
            vmin = min(0, float(ci.get("lower", 0)))
            vmax = max(1, float(ci.get("upper", 1)))
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=float(v),
                domain={"x": [0, 1], "y": [0, 1]},
                title={"text": res.get("metadata", {}).get("name", "Value")},
                number={"suffix": ""},
                gauge={
                    "axis": {"range": [vmin, vmax]},
                    "bar": {"color": "#1f77b4"},
                    "steps": [
                        {"range": [vmin, float(ci["lower"])], "color": "#e8e8e8"},
                        {"range": [float(ci["upper"]), vmax], "color": "#e8e8e8"},
                    ],
                    "threshold": {"line": {"color": "red"}, "value": vmax},
                },
            ))
            fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=200)
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass
    st.json(res)

# Display disaggregated result (table + bar chart)
if st.session_state.get("edhs_last_grouped"):
    gr = st.session_state["edhs_last_grouped"]
    st.subheader(f"Disaggregated by **{gr['group_by_column']}**")
    rows = gr.get("rows", [])
    if rows:
        tbl = pd.DataFrame([
            {
                gr["group_by_column"]: r["group_value"],
                "Estimate": r["estimate"],
                "95% CI lower": r.get("ci_lower"),
                "95% CI upper": r.get("ci_upper"),
                "N": r["population_n"],
                "N (weighted)": round(r["population_weighted_n"], 1),
            }
            for r in rows
        ])
        st.dataframe(tbl, use_container_width=True)
        try:
            import plotly.graph_objects as go
            fig = go.Figure(data=[
                go.Bar(
                    x=[str(r["group_value"]) for r in rows],
                    y=[r["estimate"] for r in rows],
                    name="Estimate",
                    marker_color="#1f77b4",
                ),
            ])
            fig.update_layout(
                title=f"{gr['indicator_id']} by {gr['group_by_column']}",
                xaxis_title=gr["group_by_column"],
                yaxis_title="Estimate",
                height=350,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass
    else:
        st.caption("No groups returned.")

# Display multiple-indicator table
if st.session_state.get("edhs_last_multi"):
    st.subheader("Multiple indicators (table)")
    rows = st.session_state["edhs_last_multi"]
    df_multi = pd.DataFrame(rows)
    st.dataframe(df_multi, use_container_width=True)
    st.download_button(
        label="Export multiple indicators (CSV)",
        data=df_multi.to_csv(index=False).encode("utf-8"),
        file_name="edhs_indicators_multi.csv",
        mime="text/csv",
    )

# Multi-country comparison for the current indicator
st.divider()
st.markdown("### 4. Multi-country comparison (same indicator)")
sessions_history = st.session_state.get("edhs_sessions_history", [])
if len(sessions_history) < 2:
    st.caption(
        "Load at least **two datasets** (or use **Try with sample data** multiple times) "
        "to compare one indicator across countries or surveys."
    )
else:
    options_sessions: dict[str, Dict[str, Any]] = {}
    current_sid = st.session_state.get("edhs_session_id")
    default_labels: list[str] = []
    for s in sessions_history:
        label_parts = []
        if s.get("country"):
            label_parts.append((s["country"] or "").upper())
        if s.get("type"):
            label_parts.append(s["type"])
        if s.get("year"):
            label_parts.append(str(s["year"]))
        label_main = " ".join(label_parts) or "Session"
        fname = s.get("filename") or ""
        label = f"{label_main} – {fname} ({s['session_id'][:8]}…)"
        options_sessions[label] = s
        if s["session_id"] == current_sid:
            default_labels.append(label)
    if len(default_labels) < 2 and len(options_sessions) >= 2:
        default_labels = list(options_sessions.keys())[:2]

    selected_labels = st.multiselect(
        "Sessions to compare",
        options=list(options_sessions.keys()),
        default=default_labels,
        help="Select two or more sessions (countries/surveys) to compare the selected indicator.",
    )

    if st.button("Compute multi-country comparison"):
        rows_cmp: list[Dict[str, Any]] = []
        for lbl in selected_labels:
            info = options_sessions[lbl]
            sid = info["session_id"]
            try:
                res = api_compute_indicator(
                    base_url,
                    tenant_id,
                    bearer_token or None,
                    sid,
                    indicator_id,
                    use_weights,
                    weight_var,
                )
                meta = res.get("metadata", {}) or {}
                ci = res.get("ci")
                rows_cmp.append(
                    {
                        "session_id": sid,
                        "country": info.get("country"),
                        "year": info.get("year"),
                        "type": info.get("type"),
                        "filename": info.get("filename"),
                        "indicator_id": res.get("indicator_id", indicator_id),
                        "name": meta.get("name", indicator_id),
                        "value": res.get("value"),
                        "ci_lower": ci.get("lower") if ci else None,
                        "ci_upper": ci.get("upper") if ci else None,
                        "population_n": res.get("population_n"),
                        "population_weighted_n": res.get("population_weighted_n"),
                    }
                )
            except Exception as e:
                st.error(f"Error for {lbl}: {e}")
        if rows_cmp:
            st.session_state["edhs_last_multi_country"] = {
                "indicator_id": indicator_id,
                "rows": rows_cmp,
            }

if st.session_state.get("edhs_last_multi_country"):
    cmp_res = st.session_state["edhs_last_multi_country"]
    st.subheader(f"Multi-country comparison – {cmp_res['indicator_id']}")
    rows = cmp_res["rows"]
    df_cmp = pd.DataFrame(rows)
    st.dataframe(df_cmp, use_container_width=True)
    try:
        import plotly.graph_objects as go

        labels = [
            " ".join(
                [
                    str(r.get("country") or "?"),
                    str(r.get("year") or ""),
                ]
            ).strip()
            for r in rows
        ]
        fig = go.Figure(
            data=[
                go.Bar(
                    x=labels,
                    y=[r["value"] for r in rows],
                    name="Value",
                    marker_color="#1f77b4",
                )
            ]
        )
        fig.update_layout(
            title=f"{rows[0].get('name', cmp_res['indicator_id'])} – multi-country",
            xaxis_title="Country / year",
            yaxis_title="Value",
            height=350,
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass

# Display map and table from spatial result
if not _choropleth_hidden and st.session_state.get("edhs_last_geojson"):
    geojson = st.session_state["edhs_last_geojson"]
    st.subheader("Choropleth map")
    html = render_choropleth(geojson, "value")
    st.components.v1.html(html, height=450)

    # Table from GeoJSON features
    rows = []
    for f in geojson.get("features", []):
        p = f.get("properties", {})
        rows.append({"admin_id": p.get("admin_id"), "value": p.get("value"), "N": p.get("population_n")})
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)

        # Export CSV
        default_name = "edhs_export.csv"
        sc = st.session_state.get("edhs_survey_country_code")
        sy = st.session_state.get("edhs_survey_year")
        if sc or sy:
            parts = [p for p in [sc or "export", str(sy) if sy else None] if p]
            default_name = f"edhs_{'_'.join(parts)}_export.csv"
        st.download_button(
            label="Export CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=default_name,
            mime="text/csv",
        )

st.divider()
st.caption("For DHS Program API data (indicators, visualizations, export), use the **DHS Program API** menu in the sidebar.")
if st.button("📡 Go to DHS Program API", key="go_dhs_from_micro"):
    st.session_state["edhs_nav_pending"] = "📡 DHS Program API"
    st.rerun()

# Legacy DHS section kept collapsed for users who had it open – redirect to nav
with st.expander("DHS Program API (legacy – use menu)", expanded=False):
    if st.button("Fetch Benin data (BJ)", key="dhs_fetch_benin", type="primary"):
        try:
            with st.spinner("Fetching Benin data from DHS Program API…"):
                dhs_resp = api_dhs_data_fetch(
                    base_url,
                    tenant_id,
                    bearer_token or None,
                    country_ids="BEN",
                    indicator_ids="FE_FRTR_W_A15,CN_ANMC_C_ANY",
                    dhs_api_key=dhs_api_key or None,
                    survey_year_start=2000,
                    survey_year_end=2024,
                )
            st.session_state["edhs_dhs_api_data"] = dhs_resp
            st.session_state["edhs_dhs_fetch_countries"] = "BEN"
            st.session_state["edhs_dhs_fetch_indicators"] = "FE_FRTR_W_A15,CN_ANMC_C_ANY"
            st.session_state.pop("edhs_dhs_indicators", None)  # Clear catalog so data table shows
            st.success(f"Loaded {len(dhs_resp.get('Data', []))} records for Benin.")
            st.rerun()
        except Exception as e:
            st.error(str(e))

    if _DHS_RESEARCH_AVAILABLE and (SUGGESTED_BY_TOPIC or COMPARISON_TEMPLATES):
        with st.expander("💡 Suggested indicators & quick templates", expanded=False):
            for topic, inds in list(SUGGESTED_BY_TOPIC.items())[:3]:
                if st.button(f"Use {topic}: " + ",".join(inds[:2]) + "…", key=f"dhs_ws_sug_{hash(topic) % 10**8}"):
                    st.session_state["edhs_dhs_fetch_indicators"] = ",".join(inds)
                    st.session_state["dhs_indicator_ids"] = ",".join(inds)
                    st.rerun()
            for idx, (label, c, i) in enumerate(COMPARISON_TEMPLATES[:3]):
                if st.button(f"Template: {label}", key=f"dhs_ws_fetch_tpl_{idx}"):
                    st.session_state["edhs_dhs_fetch_countries"] = c
                    st.session_state["edhs_dhs_fetch_indicators"] = i
                    st.session_state["dhs_country_codes"] = c
                    st.session_state["dhs_indicator_ids"] = i
                    st.rerun()

    dhs_country_input = st.text_input(
        "Country codes (comma-separated, e.g. ET,BJ,EG)",
        value=st.session_state.get("edhs_dhs_fetch_countries", "BJ"),
        key="dhs_country_codes",
        help="ISO country codes from DHS Program (ET=Ethiopia, BJ=Benin, EG=Egypt, etc.)",
    )
    dhs_indicator_input = st.text_input(
        "Indicator IDs (comma-separated)",
        value=st.session_state.get("edhs_dhs_fetch_indicators", "FE_FRTR_W_A15,CN_ANMC_C_ANY"),
        key="dhs_indicator_ids",
        help="e.g. FE_FRTR_W_A15 (ASFR 15-19), CN_ANMC_C_ANY (modern contraception)",
    )
    dhs_year_col1, dhs_year_col2 = st.columns(2)
    with dhs_year_col1:
        dhs_year_start = st.number_input(
            "Survey year from",
            min_value=1990,
            max_value=2030,
            value=2000,
            key="dhs_year_start",
        )
    with dhs_year_col2:
        dhs_year_end = st.number_input(
            "Survey year to",
            min_value=1990,
            max_value=2030,
            value=2024,
            key="dhs_year_end",
        )

    if st.button("Fetch DHS Program data", key="dhs_fetch_btn"):
        if not dhs_country_input.strip() or not dhs_indicator_input.strip():
            st.error("Enter at least one country code and one indicator ID.")
        else:
            try:
                with st.spinner("Fetching from DHS Program API…"):
                    dhs_resp = api_dhs_data_fetch(
                        base_url,
                        tenant_id,
                        bearer_token or None,
                        country_ids=dhs_country_input.strip(),
                        indicator_ids=dhs_indicator_input.strip(),
                        survey_year_start=int(dhs_year_start),
                        survey_year_end=int(dhs_year_end),
                        dhs_api_key=dhs_api_key or None,
                    )
                st.session_state["edhs_dhs_api_data"] = dhs_resp
                st.session_state["edhs_dhs_fetch_countries"] = dhs_country_input.strip()
                st.session_state["edhs_dhs_fetch_indicators"] = dhs_indicator_input.strip()
                st.session_state.pop("edhs_dhs_indicators", None)  # Clear catalog so data table shows
                st.success(f"Retrieved {len(dhs_resp.get('Data', []))} records.")
                st.rerun()
            except requests.HTTPError as e:
                detail = str(e)
                if e.response is not None:
                    try:
                        body = e.response.json()
                        detail = body.get("detail", detail)
                    except Exception:
                        pass
                st.error(detail)
            except Exception as e:
                st.error(str(e))

    if st.session_state.get("edhs_dhs_api_data"):
        dhs_data = st.session_state["edhs_dhs_api_data"]
        _countries = st.session_state.get("edhs_dhs_fetch_countries", dhs_country_input.strip())
        _indicators = st.session_state.get("edhs_dhs_fetch_indicators", dhs_indicator_input.strip())
        _render_dhs_research_ui(
            dhs_data, _countries, _indicators,
            int(dhs_year_start), int(dhs_year_end),
            key_prefix="dhs_ws",
        )
        st.download_button(
            label="Export JSON",
            data=json.dumps(dhs_data, indent=2).encode("utf-8"),
            file_name="dhs_program_export.json",
            mime="application/json",
            key="dhs_export_json",
        )

    with st.expander("Browse indicators catalog (to find IndicatorIds)", expanded=False):
        if st.button("Load indicators catalog", key="dhs_browse_indicators"):
            try:
                with st.spinner("Loading indicators…"):
                    ind_resp = api_dhs_indicators(
                        base_url, tenant_id, bearer_token or None,
                        country_ids=dhs_country_input.strip() or None,
                        per_page=50,
                        dhs_api_key=dhs_api_key or None,
                    )
                st.session_state["edhs_dhs_indicators"] = ind_resp
                st.rerun()
            except Exception as e:
                st.error(str(e))

        if st.session_state.get("edhs_dhs_indicators"):
            ind_data = st.session_state["edhs_dhs_indicators"]
            ind_list = ind_data.get("Data", [])
            if ind_list:
                st.caption("Sample indicators (first 50). Use IndicatorId in the field above.")
                sample_df = pd.DataFrame(ind_list[:50])
                cols = [c for c in ["IndicatorId", "ShortName", "Label", "Level1"] if c in sample_df.columns]
                if cols:
                    st.dataframe(sample_df[cols], use_container_width=True)

st.divider()
st.caption("Session-based processing only; no microdata is stored on the server.")
