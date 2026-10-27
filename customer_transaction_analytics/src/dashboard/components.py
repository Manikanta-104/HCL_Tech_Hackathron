"""
Reusable Streamlit UI components: page styling, KPI cards, badges and
number formatting. Styling uses semi transparent colours so it reads well
in both the light and the dark Streamlit theme.
"""

from typing import Optional

import pandas as pd
import streamlit as st

# Palette: ledger navy, teal for healthy numbers, amber and crimson for risk
COLOURS = {
    "navy": "#16324F",
    "teal": "#0E7C7B",
    "teal_light": "#5FB7B2",
    "sand": "#D9B26F",
    "amber": "#E08E2B",
    "crimson": "#C2414B",
    "slate": "#7A8B99",
}
CHANNEL_COLOURS = {"Digital": "#0E7C7B", "Branch": "#16324F", "ATM": "#D9B26F", "Unknown": "#7A8B99"}
SEGMENT_COLOURS = {"Premium": "#16324F", "Standard": "#0E7C7B", "Student": "#D9B26F", "Unknown": "#7A8B99"}
SEVERITY_COLOURS = {"High": "#C2414B", "Medium": "#E08E2B", "Low": "#5FB7B2", "None": "#7A8B99", "Unknown": "#7A8B99"}
SEQUENTIAL_SCALE = ["#EAF4F3", "#9FD2CE", "#4FA7A3", "#0E7C7B", "#16324F"]

_CSS = """
<style>
    html, body, [class*="css"] {
        font-family: "IBM Plex Sans", "Segoe UI", "Helvetica Neue", system-ui, sans-serif;
    }
    .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px; }

    .page-title {
        font-size: 1.9rem; font-weight: 650; letter-spacing: -0.01em;
        margin: 0 0 0.15rem 0; line-height: 1.2;
    }
    .page-subtitle { opacity: 0.72; font-size: 0.98rem; margin-bottom: 1.4rem; max-width: 75ch; }

    .kpi-card {
        border: 1px solid rgba(127, 127, 127, 0.22);
        border-left: 4px solid #0E7C7B;
        border-radius: 10px;
        padding: 0.85rem 1rem 0.8rem 1rem;
        background: rgba(127, 127, 127, 0.05);
        height: 100%;
    }
    .kpi-card.warn  { border-left-color: #E08E2B; }
    .kpi-card.alert { border-left-color: #C2414B; }
    .kpi-card.navy  { border-left-color: #16324F; }
    .kpi-label { font-size: 0.82rem; opacity: 0.7; margin-bottom: 0.25rem; }
    .kpi-value { font-size: 1.55rem; font-weight: 650; line-height: 1.15; font-variant-numeric: tabular-nums; }
    .kpi-sub   { font-size: 0.78rem; opacity: 0.62; margin-top: 0.25rem; }

    .section-title { font-size: 1.12rem; font-weight: 620; margin: 1.3rem 0 0.2rem 0; }
    .section-note  { font-size: 0.86rem; opacity: 0.68; margin-bottom: 0.6rem; max-width: 80ch; }

    .badge {
        display: inline-block; padding: 0.1rem 0.55rem; border-radius: 999px;
        font-size: 0.78rem; font-weight: 600; color: #fff;
    }
    .profile-row { display: flex; flex-wrap: wrap; gap: 0.5rem 1.4rem; margin: 0.2rem 0 1rem 0; font-size: 0.93rem; }
    .profile-row span b { font-weight: 620; }

    .stage {
        border: 1px solid rgba(127, 127, 127, 0.22); border-radius: 10px;
        padding: 0.7rem 0.9rem; background: rgba(127, 127, 127, 0.04); height: 100%;
    }
    .stage h4 { margin: 0 0 0.3rem 0; font-size: 0.95rem; }
    .stage p  { margin: 0; font-size: 0.84rem; opacity: 0.75; }

    .sidebar-brand { font-weight: 680; font-size: 1.15rem; letter-spacing: -0.01em; margin-bottom: 0.1rem; }
    .sidebar-caption { font-size: 0.8rem; opacity: 0.65; margin-bottom: 0.9rem; line-height: 1.35; }
</style>
"""


def apply_global_style() -> None:
    """Inject the dashboard CSS once per page render."""
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    """Title and one line description at the top of each page."""
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="page-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def section(title: str, note: str = "") -> None:
    """Section heading with an optional explanation of the metric."""
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="section-note">{note}</div>', unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: str = "", tone: str = "") -> None:
    """
    Render one KPI card.

    Args:
        label: Metric name.
        value: Pre formatted value.
        sub: Small supporting line under the value.
        tone: '', 'warn', 'alert' or 'navy' (changes the accent colour).
    """
    st.markdown(
        f'<div class="kpi-card {tone}"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


def severity_badge(severity: str) -> str:
    """HTML badge for a severity or risk level."""
    colour = SEVERITY_COLOURS.get(severity, COLOURS["slate"])
    return f'<span class="badge" style="background:{colour}">{severity}</span>'


# ---------------------------------------------------------------------- #
# Formatting helpers (all tolerate None / NaN so empty filters never crash)
# ---------------------------------------------------------------------- #
def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value))


def fmt_number(value, decimals: int = 0) -> str:
    """1234.5 -> '1,235' (or with decimals)."""
    return "n/a" if _missing(value) else f"{value:,.{decimals}f}"


def fmt_compact(value) -> str:
    """Large values in K / M form: 237739 -> '237.7K'."""
    if _missing(value):
        return "n/a"
    for divisor, suffix in ((1_000_000, "M"), (1_000, "K")):
        if abs(value) >= divisor:
            return f"{value / divisor:,.1f}{suffix}"
    return f"{value:,.0f}"


def fmt_pct(value, decimals: int = 1) -> str:
    """Value already in percent: 32.0 -> '32.0%'."""
    return "n/a" if _missing(value) else f"{value:.{decimals}f}%"


def fmt_ratio(value, decimals: int = 2) -> str:
    """Plain ratio: 0.3952 -> '0.40'."""
    return "n/a" if _missing(value) else f"{value:.{decimals}f}"


def empty_state(message: Optional[str] = None) -> None:
    """Friendly message when filters return no rows."""
    st.info(message or "No transactions match the current filters. Try widening the date range or clearing a filter.")
