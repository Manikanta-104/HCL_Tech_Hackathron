"""
Streamlit dashboard entry point.

Run from the project root:

    streamlit run src/dashboard/app.py

The sidebar holds navigation and global filters. Filters are turned into a
TransactionFilters object and passed to the SQL KPI engine.
"""

import sys
from pathlib import Path

# Make "src" importable when Streamlit runs this file directly
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from src.dashboard import data_access as dao  # noqa: E402
from src.dashboard import views  # noqa: E402
from src.dashboard.components import apply_global_style  # noqa: E402
from src.kpi.kpi_queries import TransactionFilters  # noqa: E402

PAGES = {
    "Project Home": "home",
    "KPI Dashboard": "kpi",
    "Customer Search": "customer",
    "Anomaly Alerts": "alerts",
    "Data Quality": "quality",
}
FILTER_KEYS = ["flt_dates", "flt_segments", "flt_channels", "flt_categories", "flt_risk", "flt_merchant_risk"]


def _reset_filters() -> None:
    """Clear every sidebar filter (used as a button callback)."""
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def sidebar() -> tuple:
    """
    Draw the sidebar.

    Returns:
        (selected page key, TransactionFilters)
    """
    with st.sidebar:
        st.markdown('<div class="sidebar-brand">Transaction Analytics</div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-caption">Retail banking · rule based monitoring</div>',
                    unsafe_allow_html=True)
        page_label = st.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")

        st.divider()
        st.markdown("**Filters**")
        st.caption("Applied to the KPI Dashboard and Anomaly Alerts pages.")

        options = dao.filter_options()
        dates = st.date_input(
            "Date range",
            value=(options["min_date"], options["max_date"]),
            min_value=options["min_date"],
            max_value=options["max_date"],
            key="flt_dates",
        )
        segments = st.multiselect("Customer segment", options["segments"], key="flt_segments",
                                  placeholder="All segments")
        channels = st.multiselect("Channel", options["channels"], key="flt_channels", placeholder="All channels")
        categories = st.multiselect("Category", options["categories"], key="flt_categories",
                                    placeholder="All categories")
        merchant_risk_levels = st.multiselect("Merchant risk rating", options["merchant_risk_levels"],
                                              key="flt_merchant_risk", placeholder="All merchants")
        risk_levels = st.multiselect("Transaction risk level", options["risk_levels"], key="flt_risk",
                                     placeholder="All risk levels")
        st.button("Reset filters", on_click=_reset_filters)

    # A half picked range (only the start date) gives a one element tuple
    if isinstance(dates, (list, tuple)):
        start_date = dates[0] if len(dates) >= 1 else options["min_date"]
        end_date = dates[1] if len(dates) >= 2 else options["max_date"]
    else:
        start_date = end_date = dates

    filters = TransactionFilters(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        segments=segments,
        channels=channels,
        categories=categories,
        risk_levels=risk_levels,
        merchant_risk_levels=merchant_risk_levels,
    )
    return PAGES[page_label], filters


def main() -> None:
    """Configure the page and route to the selected view."""
    st.set_page_config(page_title="Customer Transaction Analytics", page_icon="🏦", layout="wide")
    apply_global_style()

    if not dao.database_exists():
        st.error("The SQLite database was not found. Run `python main.py` from the project root first, "
                 "then refresh this page.")
        st.stop()

    page, filters = sidebar()

    if page == "home":
        views.render_home()
    elif page == "kpi":
        views.render_kpi_dashboard(filters)
    elif page == "customer":
        views.render_customer_search()
    elif page == "alerts":
        views.render_alerts(filters)
    else:
        views.render_data_quality()


main()
