"""
DHS Program API – Research features for researchers and students.

Provides: visualizations, citations, exports (Excel/PDF/Stata), glossary,
saved configs, and comparison templates.
"""

import io
import json
import os
import tempfile
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# -----------------------------------------------------------------------------
# Indicator glossary (common DHS indicators)
# -----------------------------------------------------------------------------

INDICATOR_GLOSSARY: Dict[str, Dict[str, str]] = {
    "FE_FRTR_W_A15": {
        "name": "Age-specific fertility rate: 15-19",
        "definition": "Annual number of births per 1,000 women aged 15-19.",
        "formula": "ASFR(15-19) = (Births to women 15-19 / Woman-years 15-19) × 1000",
        "topic": "Fertility",
        "interpretation": "Higher values indicate higher adolescent fertility. Used to monitor teen pregnancy.",
    },
    "CN_ANMC_C_ANY": {
        "name": "Children with any anemia",
        "definition": "Percentage of children under 5 with hemoglobin below the age-specific cutoff (any anemia).",
        "formula": "(% with mild + moderate + severe anemia)",
        "topic": "Child health",
        "interpretation": "WHO cutoffs: Hb <11.0 g/dL (6-59 mo), <10.0 (6-11 mo). High prevalence indicates malnutrition.",
    },
    "FP_CUSA_W_ANY": {
        "name": "Contraceptive prevalence, any method",
        "definition": "Percentage of married/in-union women aged 15-49 using any contraceptive method.",
        "topic": "Family planning",
        "interpretation": "Key indicator for family planning program evaluation.",
    },
    "FP_CUSM_W_MOD": {
        "name": "Contraceptive prevalence, modern methods",
        "definition": "Percentage using modern methods (pill, IUD, injectable, implant, etc.).",
        "topic": "Family planning",
        "interpretation": "Excludes traditional methods (rhythm, withdrawal).",
    },
    "CM_ECMR_C_CME": {
        "name": "Under-5 mortality rate",
        "definition": "Probability of dying between birth and exact age 5, per 1,000 live births.",
        "topic": "Child mortality",
        "interpretation": "Key SDG indicator. Declining trend indicates improved child survival.",
    },
    "RH_DELA_W_DNT": {
        "name": "Antenatal care: 4+ visits",
        "definition": "Percentage of women with 4+ ANC visits during pregnancy.",
        "topic": "Maternal health",
        "interpretation": "WHO recommends minimum 4 ANC contacts.",
    },
    "CH_VACC_C_BAS": {
        "name": "Children with basic vaccinations",
        "definition": "Percentage of children 12-23 months who received BCG, measles, and 3 doses each of DPT and polio.",
        "topic": "Immunization",
        "interpretation": "Basic vaccination package for child survival.",
    },
}

# Suggested indicators by topic
SUGGESTED_BY_TOPIC: Dict[str, List[str]] = {
    "Fertility": ["FE_FRTR_W_A15", "FP_CUSA_W_ANY", "FP_CUSM_W_MOD"],
    "Child health": ["CN_ANMC_C_ANY", "CM_ECMR_C_CME", "CH_VACC_C_BAS"],
    "Maternal health": ["RH_DELA_W_DNT", "RH_ANEM_W_ANY"],
}

# Comparison templates: (label, countries, indicators)
COMPARISON_TEMPLATES: List[Tuple[str, str, str]] = [
    ("West Africa – Fertility & FP", "BJ,BF,GH,NG,SN,TG", "FE_FRTR_W_A15,FP_CUSA_W_ANY,FP_CUSM_W_MOD"),
    ("East Africa – Child health", "ET,KE,RW,TZ,UG", "CN_ANMC_C_ANY,CM_ECMR_C_CME,CH_VACC_C_BAS"),
    ("Multi-country – Key indicators", "BJ,ET,GH,KE,NG", "FE_FRTR_W_A15,CN_ANMC_C_ANY,FP_CUSA_W_ANY"),
]


def get_dhs_dataframe(dhs_data: Dict[str, Any]) -> pd.DataFrame:
    """Extract DataFrame from DHS API response."""
    rows = dhs_data.get("Data", [])
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# -----------------------------------------------------------------------------
# Visualizations
# -----------------------------------------------------------------------------


def _chart_simple_fallback(df: pd.DataFrame) -> Optional[Any]:
    """Simple bar chart fallback when main charts fail."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None
    if df.empty or "Value" not in df.columns:
        return None
    x_vals = []
    if "SurveyYear" in df.columns and "Indicator" in df.columns:
        x_vals = [f"{str(r.get('Indicator', ''))[:25]} ({r['SurveyYear']})" for _, r in df.iterrows()]
    elif "SurveyYear" in df.columns:
        x_vals = df["SurveyYear"].astype(str).tolist()
    elif "Indicator" in df.columns:
        x_vals = df["Indicator"].str[:30].tolist()
    else:
        x_vals = [str(i) for i in range(len(df))]
    fig = go.Figure(go.Bar(x=x_vals, y=df["Value"], marker_color="#1f77b4"))
    fig.update_layout(title="Indicator values", xaxis_tickangle=-45, height=400)
    return fig


def chart_time_series(df: pd.DataFrame) -> Optional[Any]:
    """Plotly time series: indicator value by survey year (grouped by country/indicator)."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    if df.empty or "SurveyYear" not in df.columns or "Value" not in df.columns:
        return _chart_simple_fallback(df)

    sort_cols = [c for c in ["Indicator", "CountryName", "SurveyYear"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).copy()
    indicators = df["Indicator"].unique().tolist() if "Indicator" in df.columns else ["Value"]
    countries = df["CountryName"].unique().tolist() if "CountryName" in df.columns else ["All"]

    fig = go.Figure()
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    for i, (idx, grp) in enumerate(df.groupby(["Indicator", "CountryName"] if "CountryName" in df.columns else ["Indicator"])):
        ind_name = grp["Indicator"].iloc[0] if "Indicator" in grp.columns else "Value"
        country = grp["CountryName"].iloc[0] if "CountryName" in grp.columns else "All"
        label = f"{ind_name[:30]}…" if len(str(ind_name)) > 30 else str(ind_name)
        if "CountryName" in grp.columns and len(countries) > 1:
            label = f"{country} – {label}"
        fig.add_trace(
            go.Scatter(
                x=grp["SurveyYear"],
                y=grp["Value"],
                mode="lines+markers",
                name=label,
                line=dict(color=colors[i % len(colors)], width=2),
                marker=dict(size=8),
            )
        )

    fig.update_layout(
        title="Trends over time",
        xaxis_title="Survey year",
        yaxis_title="Value",
        hovermode="x unified",
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def chart_time_series_safe(df: pd.DataFrame) -> Optional[Any]:
    """Wrapper that falls back to simple chart on error."""
    try:
        fig = chart_time_series(df)
        return fig if fig is not None else _chart_simple_fallback(df)
    except Exception:
        return _chart_simple_fallback(df)


def chart_country_comparison(df: pd.DataFrame, group_by: str = "Indicator") -> Optional[Any]:
    """Plotly bar chart: compare countries or indicators."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None

    if df.empty or "Value" not in df.columns:
        return None

    if group_by == "Indicator" and "Indicator" in df.columns and "CountryName" in df.columns:
        pivot = df.pivot_table(index="CountryName", columns="Indicator", values="Value", aggfunc="first")
        pivot = pivot.fillna(0)
        cols = [c for c in pivot.columns[:8] if pivot[c].notna().any()]
        if cols:
            fig = go.Figure(data=[
                go.Bar(name=str(c)[:40], x=pivot.index.astype(str), y=pivot[c].values)
                for c in cols
            ])
            fig.update_layout(barmode="group", title="Country comparison by indicator", height=400)
        else:
            fig = go.Figure(go.Bar(x=df["CountryName"].astype(str) if "CountryName" in df.columns else range(len(df)), y=df["Value"], marker_color="#1f77b4"))
            fig.update_layout(title="Values by country", height=400)
    else:
        x_col = "CountryName" if "CountryName" in df.columns else "SurveyYear"
        fig = go.Figure(go.Bar(x=df[x_col], y=df["Value"], marker_color="#1f77b4"))
        fig.update_layout(title="Values by " + x_col, xaxis_title=x_col, height=400)

    fig.update_layout(hovermode="x unified", xaxis_tickangle=-45)
    return fig


def chart_country_comparison_safe(df: pd.DataFrame) -> Optional[Any]:
    """Wrapper that falls back to simple chart on error."""
    try:
        fig = chart_country_comparison(df)
        return fig if fig is not None else _chart_simple_fallback(df)
    except Exception:
        return _chart_simple_fallback(df)


# -----------------------------------------------------------------------------
# Additional visualizations
# -----------------------------------------------------------------------------


def chart_heatmap(df: pd.DataFrame, mode: str = "country_indicator") -> Optional[Any]:
    """Heatmap: country × indicator or year × indicator matrix."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None
    if df.empty or "Value" not in df.columns:
        return None
    if mode == "year_indicator" and "SurveyYear" in df.columns and "Indicator" in df.columns:
        pivot = df.pivot_table(index="SurveyYear", columns="Indicator", values="Value", aggfunc="first")
    elif "CountryName" in df.columns and "Indicator" in df.columns:
        pivot = df.pivot_table(index="CountryName", columns="Indicator", values="Value", aggfunc="first")
    else:
        return None
    pivot = pivot.fillna(0)
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[str(c)[:30] for c in pivot.columns],
        y=pivot.index.astype(str),
        colorscale="Blues",
        hoverongaps=False,
    ))
    fig.update_layout(title="Heatmap: values by dimension", height=400, xaxis_tickangle=-45)
    return fig


def chart_sankey(df: pd.DataFrame) -> Optional[Any]:
    """Sankey: Country → Indicator flow (value as flow amount)."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None
    if df.empty or "Value" not in df.columns:
        return None
    src_col = "CountryName" if "CountryName" in df.columns else "SurveyYear"
    tgt_col = "Indicator" if "Indicator" in df.columns else "IndicatorId"
    if src_col not in df.columns or tgt_col not in df.columns:
        return None
    df = df.copy()
    df["source"] = df[src_col].astype(str)
    df["target"] = df[tgt_col].astype(str).str[:25]
    df["value"] = pd.to_numeric(df["Value"], errors="coerce").fillna(0)
    agg = df.groupby(["source", "target"])["value"].sum().reset_index()
    all_labels = list(dict.fromkeys(agg["source"].tolist() + agg["target"].tolist()))
    label_to_idx = {lbl: i for i, lbl in enumerate(all_labels)}
    fig = go.Figure(data=[go.Sankey(
        node=dict(label=all_labels),
        link=dict(
            source=[label_to_idx[s] for s in agg["source"]],
            target=[label_to_idx[t] for t in agg["target"]],
            value=agg["value"].tolist(),
        ),
    )])
    fig.update_layout(title="Sankey: Country → Indicator", height=450)
    return fig


def chart_radar(df: pd.DataFrame, country: Optional[str] = None) -> Optional[Any]:
    """Radar chart: multiple indicators per country (country profile)."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None
    if df.empty or "Value" not in df.columns or "Indicator" not in df.columns:
        return None
    if country and "CountryName" in df.columns:
        df = df[df["CountryName"].astype(str) == str(country)]
    if df.empty:
        return None
    inds = df["Indicator"].str[:25].tolist()
    vals = df["Value"].tolist()
    if len(inds) < 3:
        return None
    fig = go.Figure(data=go.Scatterpolar(
        r=vals + [vals[0]],
        theta=inds + [inds[0]],
        fill="toself",
        name=country or "Profile",
    ))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True)), title="Radar: indicator profile", height=400)
    return fig


def chart_box(df: pd.DataFrame, by: str = "Indicator") -> Optional[Any]:
    """Box plot: distribution by country, year, or indicator."""
    try:
        import plotly.express as px
    except ImportError:
        return None
    if df.empty or "Value" not in df.columns:
        return None
    col = "CountryName" if by == "country" and "CountryName" in df.columns else "SurveyYear" if by == "year" and "SurveyYear" in df.columns else "Indicator"
    if col not in df.columns:
        col = "Indicator" if "Indicator" in df.columns else "CountryName" if "CountryName" in df.columns else None
    if not col:
        return None
    fig = px.box(df, x=col, y="Value", title=f"Box plot by {col}")
    fig.update_layout(height=400, xaxis_tickangle=-45)
    return fig


def chart_small_multiples(df: pd.DataFrame, facet_col: str = "CountryName") -> Optional[Any]:
    """Small multiples: same bar chart repeated per facet (country or year)."""
    try:
        import plotly.express as px
    except ImportError:
        return None
    if df.empty or "Value" not in df.columns:
        return None
    fc = "CountryName" if facet_col == "country" and "CountryName" in df.columns else "SurveyYear" if facet_col == "year" and "SurveyYear" in df.columns else None
    xc = "Indicator" if "Indicator" in df.columns else "SurveyYear" if "SurveyYear" in df.columns else None
    if not fc or not xc:
        return None
    fig = px.bar(df, x=xc, y="Value", facet_col=fc, facet_col_wrap=3)
    fig.update_layout(height=500, xaxis_tickangle=-45)
    return fig


def chart_treemap(df: pd.DataFrame) -> Optional[Any]:
    """Treemap: hierarchical view (country → indicator)."""
    try:
        import plotly.express as px
    except ImportError:
        return None
    if df.empty or "Value" not in df.columns:
        return None
    path_cols = []
    if "CountryName" in df.columns:
        path_cols.append("CountryName")
    if "Indicator" in df.columns:
        path_cols.append("Indicator")
    if not path_cols:
        return None
    fig = px.treemap(df, path=path_cols, values="Value", title="Treemap: Country → Indicator")
    fig.update_layout(height=450)
    return fig


def chart_scatter(df: pd.DataFrame, x_ind: Optional[str] = None, y_ind: Optional[str] = None) -> Optional[Any]:
    """Scatter: two indicators (e.g. fertility vs contraception)."""
    try:
        import plotly.express as px
    except ImportError:
        return None
    if df.empty or "Value" not in df.columns or "Indicator" not in df.columns:
        return None
    pivot = df.pivot_table(index=["CountryName", "SurveyYear"] if "CountryName" in df.columns and "SurveyYear" in df.columns else "SurveyYear", columns="Indicator", values="Value", aggfunc="first")
    if pivot.shape[1] < 2:
        return None
    x_col = pivot.columns[0] if not x_ind else next((c for c in pivot.columns if x_ind in str(c)), pivot.columns[0])
    y_col = pivot.columns[1] if not y_ind else next((c for c in pivot.columns if y_ind in str(c)), pivot.columns[min(1, len(pivot.columns) - 1)])
    pivot = pivot.reset_index()
    fig = px.scatter(pivot, x=x_col, y=y_col, hover_data=pivot.columns.tolist(), title=f"Scatter: {x_col[:20]} vs {y_col[:20]}")
    fig.update_layout(height=400)
    return fig


def chart_gauge(value: float, title: str = "Indicator", min_val: float = 0, max_val: float = 100) -> Optional[Any]:
    """Gauge / KPI: single value with range."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": title},
        gauge={"axis": {"range": [min_val, max_val]}, "bar": {"color": "#1f77b4"}},
    ))
    fig.update_layout(height=250)
    return fig


def chart_animated_time_series(df: pd.DataFrame) -> Optional[Any]:
    """Animated time series: year slider or play button."""
    try:
        import plotly.express as px
    except ImportError:
        return None
    if df.empty or "SurveyYear" not in df.columns or "Value" not in df.columns:
        return None
    ind_col = "Indicator" if "Indicator" in df.columns else None
    if not ind_col:
        return None
    fig = px.line(df, x="SurveyYear", y="Value", color=ind_col, title="Animated time series")
    fig.update_layout(height=400)
    return fig


def chart_sunburst(df: pd.DataFrame) -> Optional[Any]:
    """Sunburst: nested hierarchy (Level1 → Level2 → indicator or Country → Indicator)."""
    try:
        import plotly.express as px
    except ImportError:
        return None
    if df.empty or "Value" not in df.columns:
        return None
    path_cols = []
    if "Level1" in df.columns:
        path_cols.append("Level1")
    if "Level2" in df.columns:
        path_cols.append("Level2")
    if "CountryName" in df.columns:
        path_cols.append("CountryName")
    if "Indicator" in df.columns:
        path_cols.append("Indicator")
    if not path_cols:
        path_cols = ["CountryName", "Indicator"] if "CountryName" in df.columns and "Indicator" in df.columns else ["Indicator"]
    if not path_cols:
        return None
    path_cols = [c for c in path_cols if c in df.columns]
    if not path_cols:
        return None
    fig = px.sunburst(df, path=path_cols, values="Value", title="Sunburst: indicator taxonomy")
    fig.update_layout(height=450)
    return fig


# -----------------------------------------------------------------------------
# Citation generator
# -----------------------------------------------------------------------------

def format_citation(
    countries: str,
    indicators: str,
    year_start: int,
    year_end: int,
    style: str = "apa",
) -> str:
    """Generate citation for DHS Program data."""
    date_str = datetime.now().strftime("%B %d, %Y")
    if style == "apa":
        return (
            "The DHS Program. (n.d.). STATcompiler. Retrieved "
            f"{date_str}, from https://www.statcompiler.com/. "
            f"Data extracted for countries {countries}, indicators {indicators}, "
            f"survey years {year_start}-{year_end}."
        )
    elif style == "chicago":
        return (
            "The DHS Program. STATcompiler. Accessed "
            f"{date_str}. https://www.statcompiler.com/. "
            f"Countries: {countries}. Indicators: {indicators}. Years: {year_start}-{year_end}."
        )
    else:  # harvard
        return (
            "The DHS Program (n.d.) STATcompiler. Available at: https://www.statcompiler.com/ "
            f"(Accessed: {date_str}). Countries: {countries}. Indicators: {indicators}. "
            f"Survey years: {year_start}-{year_end}."
        )


# -----------------------------------------------------------------------------
# Shareable URL
# -----------------------------------------------------------------------------

def build_shareable_params(
    countries: str,
    indicators: str,
    year_start: int,
    year_end: int,
) -> str:
    """Build URL query string for shareable link."""
    return urllib.parse.urlencode({
        "countries": countries,
        "indicators": indicators,
        "year_start": year_start,
        "year_end": year_end,
    })


# -----------------------------------------------------------------------------
# Export: Excel
# -----------------------------------------------------------------------------

def export_excel(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    sheet_data: str = "Data",
    sheet_meta: str = "Metadata",
) -> bytes:
    """Export DataFrame and metadata to Excel."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError("Install openpyxl: pip install openpyxl")

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_data, index=False)
        meta_df = pd.DataFrame([{"key": k, "value": str(v)} for k, v in metadata.items()])
        meta_df.to_excel(writer, sheet_name=sheet_meta, index=False)
    return buf.getvalue()


# -----------------------------------------------------------------------------
# Export: PDF report
# -----------------------------------------------------------------------------

def export_pdf_report(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    title: str = "DHS Program Data Export",
) -> bytes:
    """Generate a simple PDF report with table and metadata."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        raise ImportError("Install reportlab: pip install reportlab")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=0.75 * inch, leftMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Metadata", styles["Heading2"]))
    meta_text = "<br/>".join(f"<b>{k}:</b> {v}" for k, v in metadata.items())
    story.append(Paragraph(meta_text, styles["Normal"]))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Data", styles["Heading2"]))
    if not df.empty:
        cols = list(df.columns)[:10]
        data = [cols] + df[cols].head(50).astype(str).values.tolist()
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No data.", styles["Normal"]))

    doc.build(story)
    return buf.getvalue()


# -----------------------------------------------------------------------------
# Export: Stata/SPSS-ready
# -----------------------------------------------------------------------------

def export_stata_ready(df: pd.DataFrame) -> bytes:
    """Export CSV in Stata-friendly format (clean column names, no special chars)."""
    out = df.copy()
    out.columns = [c.replace(" ", "_").replace(".", "_")[:32] for c in out.columns]
    return out.to_csv(index=False).encode("utf-8")


def export_spss_sav(df: pd.DataFrame) -> Optional[bytes]:
    """Export to SPSS .sav format if pyreadstat available."""
    try:
        import pyreadstat
    except ImportError:
        return None
    # pyreadstat.write_sav requires a file path, not BytesIO
    with tempfile.NamedTemporaryFile(suffix=".sav", delete=False) as tmp:
        path = tmp.name
    try:
        pyreadstat.write_sav(df, path)
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
