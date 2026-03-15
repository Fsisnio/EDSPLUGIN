"""
Streamlit MVP for the Hybrid EDHS Platform.

Connects to the FastAPI backend to:
- Upload DHS/EDHS datasets (or create a mock session)
- Select country, indicator, and weighting
- Display indicator result, chart, and choropleth map
- Export results to CSV
"""

import json
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st

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
        st.caption("KPI cards (latest values)")
        kpi_vals = df.nlargest(5, "SurveyYear" if "SurveyYear" in df.columns else "Value") if "SurveyYear" in df.columns else df.head(5)
        kpi_cols = st.columns(min(5, len(kpi_vals)))
        for i, (_, row) in enumerate(kpi_vals.iterrows()):
            with kpi_cols[i]:
                v = row.get("Value", 0)
                lbl = str(row.get("Indicator", row.get("IndicatorId", "Value")))[:25]
                fig_g = chart_gauge(float(v), lbl, min_val=0, max_val=max(100, float(v) * 1.2) if isinstance(v, (int, float)) else 100)
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

# Map 3-letter ISO codes to 2-letter DHS country codes (api.dhsprogram.com uses ISO 3166-1 alpha-2)
_ISO3_TO_DHS: Dict[str, str] = {
    "ETH": "ET", "BEN": "BJ", "EGY": "EG", "GHA": "GH", "KEN": "KE",
    "NGA": "NG", "TZA": "TZ", "UGA": "UG", "ZAF": "ZA", "BFA": "BF",
    "MLI": "ML", "RWA": "RW", "SEN": "SN", "TCD": "TD", "CIV": "CI",
    "CMR": "CM", "COD": "CD", "COG": "CG", "MAR": "MA", "TUN": "TN",
}


def _to_dhs_country_code(raw: str) -> str:
    """Convert country input (2- or 3-letter) to DHS 2-letter code."""
    s = (raw or "").strip().upper()
    if not s:
        return "ET"
    if len(s) >= 3 and s in _ISO3_TO_DHS:
        return _ISO3_TO_DHS[s]
    return s[:2]


def get_headers(tenant_id: str, bearer_token: Optional[str]) -> Dict[str, str]:
    h = {"X-Tenant-ID": tenant_id}
    if bearer_token:
        h["Authorization"] = f"Bearer {bearer_token}"
    return h


def api_health(base_url: str, tenant_id: str, bearer_token: Optional[str]) -> bool:
    try:
        r = requests.get(
            f"{base_url}/health",
            headers=get_headers(tenant_id, bearer_token),
            timeout=5,
        )
        return r.status_code == 200
    except Exception:
        return False


def api_list_indicators(
    base_url: str, tenant_id: str, bearer_token: Optional[str]
) -> List[Dict[str, Any]]:
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
) -> Dict[str, Any]:
    """List indicators from DHS Program API (via backend proxy)."""
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
        headers=get_headers(tenant_id, bearer_token),
        params=params if params else None,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def api_dhs_countries(
    base_url: str,
    tenant_id: str,
    bearer_token: Optional[str],
    **params: Any,
) -> Dict[str, Any]:
    """List countries from DHS Program API (via backend proxy)."""
    r = requests.get(
        f"{base_url}/dhs-api/countries",
        headers=get_headers(tenant_id, bearer_token),
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
    r = requests.get(
        f"{base_url}/dhs-api/data",
        headers=get_headers(tenant_id, bearer_token),
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
    r.raise_for_status()
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
    page_title="EDHS Hybrid Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar: connection (in expander to reduce clutter)
with st.sidebar.expander("Backend connection", expanded=False):
    base_url = st.text_input(
        "API base URL",
        value="http://127.0.0.1:8000/api/v1",
        help="FastAPI backend URL.",
    )
    tenant_id = st.text_input("Tenant ID", value="demo-tenant")
    bearer_token = st.text_input(
        "JWT token (optional)",
        type="password",
        help="Bearer token for authenticated deployments.",
    )
    if st.button("Check connection"):
        ok = api_health(base_url, tenant_id, bearer_token or None)
        st.session_state["edhs_connection_ok"] = ok
        if ok:
            st.success("Backend is reachable.")
        else:
            st.error("Cannot reach backend. Check URL and tenant.")

# Connection status badge (lazy check on first load; short timeout so app stays responsive)
if "edhs_connection_ok" not in st.session_state:
    try:
        r = requests.get(
            f"{base_url}/health",
            headers=get_headers(tenant_id, bearer_token or None),
            timeout=2,
        )
        st.session_state["edhs_connection_ok"] = r.status_code == 200
    except Exception:
        st.session_state["edhs_connection_ok"] = False
if st.session_state.get("edhs_connection_ok"):
    st.sidebar.caption("🟢 Backend connected")
else:
    st.sidebar.caption("🔴 Backend not reached")

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
            dhs_resp = api_dhs_data(
                base_url,
                tenant_id,
                bearer_token or None,
                country_ids=country_code_dhs,
                indicator_ids="FE_FRTR_W_A15,CN_ANMC_C_ANY",  # Common indicators
                survey_year_start=2000,
                survey_year_end=2024,
            )
        st.session_state["edhs_dhs_api_data"] = dhs_resp
        st.session_state["edhs_dhs_fetch_countries"] = country_code_dhs
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

    st.sidebar.caption(f"Fichier : **{uploaded_file.name}** — cliquez sur le bouton ci-dessous pour **l’envoyer au serveur** et créer la session.")
    if st.sidebar.button("Upload dataset", type="primary"):
        if not file_bytes:
            st.session_state["edhs_upload_error"] = "Le fichier est vide. Resélectionnez le fichier et réessayez."
            st.rerun()
        try:
            with st.sidebar.spinner("Envoi en cours…"):
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
        # Ne pas effacer l'historique des sessions pour la comparaison multi-pays
        st.rerun()
else:
    st.sidebar.info(
        "Create a session: **Try with sample data**, **Load from URL**, or upload a .dta/.sav file and click **Upload dataset**."
    )

# Main area
st.markdown(
    '<div style="text-align: center;">'
    '<h1 style="margin-bottom: 0.25rem;">Hybrid EDHS Platform</h1>'
    '<p style="color: #666; font-size: 0.9rem;">Upload data, choose an indicator, and view results with optional map and export.</p>'
    '</div>',
    unsafe_allow_html=True,
)
st.markdown("---")
# Toujours afficher un message pour vérifier que la page se charge
if not st.session_state.get("edhs_session_id"):
    st.info(
        "👈 **Ouvrez la barre latérale** (icône en haut à gauche) puis créez une session : **Try with sample data**, **Load from URL**, ou envoyez un fichier .dta/.sav."
    )

# Show upload error prominently so it's not missed
if st.session_state.get("edhs_upload_error"):
    st.error("**Erreur d’upload :** " + st.session_state["edhs_upload_error"])
    st.caption(
        "Ouvrez la **barre latérale** (icône ‹ en haut à gauche) pour resélectionner un fichier .dta/.sav et cliquer sur **Upload dataset**. "
        "Ou utilisez le bouton ci‑dessous pour continuer avec des données d'exemple."
    )
    if st.button("Essayer avec des données d'exemple (sans fichier)", type="primary", key="sample_after_error"):
        try:
            resp = api_mock_session(
                base_url,
                tenant_id,
                bearer_token or None,
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
            history.append(
                {
                    "session_id": resp["session_id"],
                    "country": resp.get("survey_country_code"),
                    "year": resp.get("survey_year"),
                    "type": resp.get("survey_type"),
                    "filename": resp.get("filename", "sample"),
                }
            )
            st.session_state.pop("edhs_upload_error", None)
            st.success("Session créée. Vous pouvez maintenant choisir un indicateur.")
            st.rerun()
        except Exception as e:
            st.error(str(e))
    st.markdown("---")

if not session_id:
    st.markdown("---")
    # If a file is already selected in the sidebar, offer to send it from the main area
    upload_name = st.session_state.get("edhs_upload_file_name")
    upload_bytes = st.session_state.get("edhs_upload_file_bytes")
    if upload_name and upload_bytes:
        st.info(f"**Fichier sélectionné :** {upload_name} — envoyez-le au serveur pour créer la session.")
        if st.button("Envoyer le fichier et créer la session", type="primary", key="upload_from_main"):
            try:
                st.info("Envoi du fichier en cours (cela peut prendre 1 à 2 min pour un gros fichier)…")
                st.warning("Ne fermez pas cette page.")
                with st.spinner("Envoi en cours…"):
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
                st.success("Session créée. Vous pouvez maintenant choisir un indicateur.")
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
    st.markdown("### Démarrer")
    st.markdown(
        "**Vérifiez d’abord :** le backend doit être démarré (ex. `uvicorn edhs_core.main:app --reload`) et l’URL dans la barre latérale doit pointer vers l’API (ex. `http://127.0.0.1:8000/api/v1`)."
    )
    st.markdown(
        "1. **Vérifier la connexion** (barre latérale à gauche) — l’URL de l’API doit être correcte.  \n"
        "2. **Créer une session** — dans la barre latérale : **Try with sample data**, **Load from URL** (lien direct .dta/.sav/.zip), ou envoyer un fichier .dta/.sav puis **Upload dataset**.  \n"
        "3. **Choisir un indicateur** puis lancer **Compute** ou **Compute & show map**."
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

    # DHS Program API – visible even without a session (no microdata required)
    st.markdown("---")
    st.markdown("## DHS Program API – Indicators & Data Export")
    st.caption(
        "Browse indicators and fetch aggregated data from the DHS Program STATcompiler "
        "(api.dhsprogram.com). No session required."
    )
    with st.expander("DHS Program API – Browse & Export", expanded=True):
        if st.button("Fetch Benin data (BJ)", key="dhs_fetch_benin_no_session", type="primary"):
            try:
                with st.spinner("Fetching Benin data from DHS Program API…"):
                    dhs_resp = api_dhs_data(
                        base_url,
                        tenant_id,
                        bearer_token or None,
                        country_ids="BJ",
                        indicator_ids="FE_FRTR_W_A15,CN_ANMC_C_ANY",
                        survey_year_start=2000,
                        survey_year_end=2024,
                    )
                st.session_state["edhs_dhs_api_data"] = dhs_resp
                st.session_state["edhs_dhs_fetch_countries"] = "BJ"
                st.session_state["edhs_dhs_fetch_indicators"] = "FE_FRTR_W_A15,CN_ANMC_C_ANY"
                st.session_state.pop("edhs_dhs_indicators", None)  # Clear catalog so data table shows
                st.success(f"Loaded {len(dhs_resp.get('Data', []))} records for Benin.")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    # Suggested indicators & quick templates
    if _DHS_RESEARCH_AVAILABLE and (SUGGESTED_BY_TOPIC or COMPARISON_TEMPLATES):
        with st.expander("💡 Suggested indicators & quick templates", expanded=False):
            for topic, inds in list(SUGGESTED_BY_TOPIC.items())[:3]:
                if st.button(f"Use {topic}: " + ",".join(inds[:2]) + "…", key=f"dhs_ns_sug_{hash(topic) % 10**8}"):
                    st.session_state["edhs_dhs_fetch_indicators"] = ",".join(inds)
                    st.session_state["dhs_indicator_ids_no_session"] = ",".join(inds)
                    st.rerun()
            for idx, (label, c, i) in enumerate(COMPARISON_TEMPLATES[:3]):
                if st.button(f"Template: {label}", key=f"dhs_ns_fetch_tpl_{idx}"):
                    st.session_state["edhs_dhs_fetch_countries"] = c
                    st.session_state["edhs_dhs_fetch_indicators"] = i
                    st.session_state["dhs_country_codes_no_session"] = c
                    st.session_state["dhs_indicator_ids_no_session"] = i
                    st.rerun()

    dhs_country_input = st.text_input(
        "Country codes (comma-separated, e.g. ET,BJ,EG)",
        value=st.session_state.get("edhs_dhs_fetch_countries", "BJ"),
        key="dhs_country_codes_no_session",
        help="ISO country codes from DHS Program (ET=Ethiopia, BJ=Benin, EG=Egypt, etc.)",
    )
    dhs_indicator_input = st.text_input(
        "Indicator IDs (comma-separated)",
        value=st.session_state.get("edhs_dhs_fetch_indicators", "FE_FRTR_W_A15,CN_ANMC_C_ANY"),
        key="dhs_indicator_ids_no_session",
        help="e.g. FE_FRTR_W_A15 (ASFR 15-19), CN_ANMC_C_ANY (modern contraception)",
    )
    dhs_year_col1, dhs_year_col2 = st.columns(2)
    with dhs_year_col1:
        dhs_year_start = st.number_input(
            "Survey year from",
            min_value=1990,
            max_value=2030,
            value=2000,
            key="dhs_year_start_no_session",
        )
    with dhs_year_col2:
        dhs_year_end = st.number_input(
            "Survey year to",
            min_value=1990,
            max_value=2030,
            value=2024,
            key="dhs_year_end_no_session",
        )

    if st.button("Fetch DHS Program data", key="dhs_fetch_btn_no_session"):
        if not dhs_country_input.strip() or not dhs_indicator_input.strip():
            st.error("Enter at least one country code and one indicator ID.")
        else:
            try:
                with st.spinner("Fetching from DHS Program API…"):
                    dhs_resp = api_dhs_data(
                        base_url,
                        tenant_id,
                        bearer_token or None,
                        country_ids=dhs_country_input.strip(),
                        indicator_ids=dhs_indicator_input.strip(),
                        survey_year_start=int(dhs_year_start),
                        survey_year_end=int(dhs_year_end),
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
            key_prefix="dhs_ns",
        )
        st.download_button(
            label="Export JSON",
            data=json.dumps(dhs_data, indent=2).encode("utf-8"),
            file_name="dhs_program_export.json",
            mime="application/json",
            key="dhs_export_json_no_session",
        )

    st.stop()

# Load indicators once
if "edhs_indicators" not in st.session_state:
    try:
        st.session_state["edhs_indicators"] = api_list_indicators(
            base_url, tenant_id, bearer_token or None
        )
    except Exception as e:
        st.error("**Impossible de charger les indicateurs.** Vérifiez que le backend est démarré (URL dans la barre latérale) et réessayez.")
        st.caption(str(e))
        if st.button("Réessayer", key="retry_indicators"):
            st.session_state.pop("edhs_indicators", None)
            st.rerun()
        if st.button("Effacer la session et recommencer", key="clear_after_indicator_fail"):
            st.session_state.pop("edhs_session_id", None)
            st.session_state.pop("edhs_indicators", None)
            st.session_state.pop("edhs_survey_country_code", None)
            st.session_state.pop("edhs_survey_year", None)
            st.session_state.pop("edhs_survey_type", None)
            st.rerun()
        st.stop()

indicators = st.session_state["edhs_indicators"]
if not indicators:
    st.warning("Aucun indicateur disponible. Vérifiez le backend.")
    if st.button("Réessayer", key="retry_indicators2"):
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
        f"**Session active : {label}** — 1) Choisissez un indicateur, 2) (optionnel) ajustez les options avancées, 3) lancez **Compute** ou **Compute & show map**."
    )
else:
    st.success(
        f"**Session active**{source_label} — 1) Choisissez un indicateur, 2) (optionnel) ajustez les options avancées, 3) lancez **Compute** ou **Compute & show map**."
    )

st.markdown("### 2. Choisir l'indicateur et le niveau géographique")

# Selection (mode simple)
col1, col2 = st.columns([2, 1])

with col1:
    ind_options = {f"{i['id']} – {i['name']}": i["id"] for i in indicators}
    ind_label = st.selectbox("Indicator", list(ind_options.keys()))
    indicator_id = ind_options[ind_label]

with col2:
    country_code = st.text_input(
        "Country (ISO)",
        value=st.session_state.get("edhs_survey_country_code") or "ETH",
        max_chars=3,
    )
    admin_level = st.number_input("Admin level", min_value=0, max_value=5, value=1)

# Options avancées (poids et colonnes d'admin)
with st.expander("Options avancées (poids DHS et colonnes d'unités admin)", expanded=False):
    st.caption("La plupart du temps, vous pouvez garder ces valeurs par défaut.")
    col_a, col_b = st.columns(2)
    with col_a:
        use_weights = st.checkbox("Use DHS weights", value=True)
        weight_var = st.text_input("Weight var", value="v005")
    with col_b:
        micro_admin = st.text_input("Microdata admin column", value="admin1_code")
        boundary_admin = st.text_input("Boundary admin column", value="admin_id")

st.markdown("### 3. Désagréger et calculer l'indicateur")

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

cols_btn = st.columns(3)

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
    # By défaut, on propose le même indicateur ; l'utilisateur peut en ajouter d'autres.
    multi_labels = list(ind_options.keys())
    default_multi = [ind_label]
    selected_multi = st.multiselect(
        "Multiple indicators (table)",
        options=multi_labels,
        default=default_multi,
        help="Sélectionnez un ou plusieurs indicateurs à calculer et à afficher sous forme de tableau.",
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
                st.error(f"Erreur pour {lbl}: {e}")
        if rows_multi:
            st.session_state["edhs_last_multi"] = rows_multi

# Compute spatial and show map
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
        "Chargez au moins **deux fichiers** (ou utilisez plusieurs fois le bouton *Try with sample data*) "
        "pour comparer un indicateur entre pays / enquêtes."
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
        "Sessions à comparer",
        options=list(options_sessions.keys()),
        default=default_labels,
        help="Sélectionnez deux sessions ou plus (pays/enquêtes) pour comparer l'indicateur choisi.",
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
                st.error(f"Erreur pour {lbl}: {e}")
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
if st.session_state.get("edhs_last_geojson"):
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
st.markdown("---")
st.markdown("## DHS Program API – Indicators & Data Export")

st.caption(
    "Browse indicators and fetch aggregated data from the DHS Program STATcompiler "
    "(api.dhsprogram.com). Data is proxied through the backend. Requires DHS_PROGRAM_API_KEY configured."
)

with st.expander("DHS Program API – Browse & Export", expanded=True):
    # Quick fetch: Benin (BJ) – one-click demo
    if st.button("Fetch Benin data (BJ)", key="dhs_fetch_benin", type="primary"):
        try:
            with st.spinner("Fetching Benin data from DHS Program API…"):
                dhs_resp = api_dhs_data(
                    base_url,
                    tenant_id,
                    bearer_token or None,
                    country_ids="BJ",
                    indicator_ids="FE_FRTR_W_A15,CN_ANMC_C_ANY",
                    survey_year_start=2000,
                    survey_year_end=2024,
                )
            st.session_state["edhs_dhs_api_data"] = dhs_resp
            st.session_state["edhs_dhs_fetch_countries"] = "BJ"
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
                    dhs_resp = api_dhs_data(
                        base_url,
                        tenant_id,
                        bearer_token or None,
                        country_ids=dhs_country_input.strip(),
                        indicator_ids=dhs_indicator_input.strip(),
                        survey_year_start=int(dhs_year_start),
                        survey_year_end=int(dhs_year_end),
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
