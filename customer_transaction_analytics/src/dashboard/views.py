"""
Page renderers for the Streamlit dashboard.

Pages
    Project Home     what the platform does, architecture, latest run
    KPI Dashboard    KPI cards and interactive charts for the five KPIs
    Customer Search  customer 360 view with history and alerts
    Anomaly Alerts   rule based alerts, risk levels and the alert queue
    Data Quality     cleaning report, schema validation, quarantined rows
"""

import pandas as pd
import streamlit as st

from src.dashboard import charts
from src.dashboard import data_access as dao
from src.dashboard.components import (
    empty_state,
    fmt_compact,
    fmt_number,
    fmt_pct,
    fmt_ratio,
    kpi_card,
    page_header,
    section,
    severity_badge,
)
from src.kpi.kpi_queries import TransactionFilters

ARCHITECTURE_DOT = """
digraph G {
    rankdir=LR; bgcolor="transparent"; nodesep=0.35; ranksep=0.45;
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11,
          color="#16324F", fillcolor="#EAF4F3", fontcolor="#16324F", margin="0.18,0.08"];
    edge [color="#7A8B99", arrowsize=0.7];

    raw     [label="CSV landing zone\\ndata/raw"];
    ingest  [label="Ingestion\\nschema + relationships"];
    clean   [label="Cleaning & validation\\nnulls, dups, types"];
    feat    [label="Feature engineering\\ntime, merchant, geo, channel"];
    anomaly [label="Rule based\\nanomaly detection", fillcolor="#F6E3C5"];
    db      [label="SQLite\\nstar schema + views", fillcolor="#16324F", fontcolor="white"];
    kpi     [label="KPI engine\\nSQL queries"];
    dash    [label="Streamlit dashboard\\nPlotly charts", fillcolor="#0E7C7B", fontcolor="white"];

    raw -> ingest -> clean -> feat;
    feat -> anomaly -> db;
    feat -> db;
    db -> kpi -> dash;
    db -> dash [style=dashed, label=" alerts", fontsize=9, fontcolor="#7A8B99"];
}
"""


# ====================================================================== #
# Project home
# ====================================================================== #
def render_home() -> None:
    """Landing page."""
    page_header(
        "Customer Transaction Analytics",
        "A batch analytics platform for a retail bank. Raw transaction files are validated, cleaned and enriched, "
        "stored in SQLite, measured with SQL KPIs and screened by business rules for unusual behaviour.",
    )

    st.graphviz_chart(ARCHITECTURE_DOT)

    run = dao.latest_pipeline_run()
    section("Latest pipeline run", f"Run {run.get('run_id', 'n/a')} finished at {run.get('finished_at', 'n/a')}.")
    cols = st.columns(5)
    with cols[0]:
        kpi_card("Status", str(run.get("status", "n/a")), "all seven stages", tone="navy")
    with cols[1]:
        kpi_card("Raw rows ingested", fmt_number(run.get("raw_rows")), "across all four CSV files")
    with cols[2]:
        kpi_card("Clean transactions", fmt_number(run.get("clean_transactions")), "loaded to SQLite")
    with cols[3]:
        rejected = run.get("rejected_records", 0)
        kpi_card("Rejected records", fmt_number(rejected), "quarantined with reason", tone="warn" if rejected else "")
    with cols[4]:
        kpi_card("Alerts generated", fmt_number(run.get("alerts_generated")), f"in {run.get('duration_seconds', 0)} s",
                 tone="alert")

    left, right = st.columns([1, 1])
    with left:
        section("Data model", "Star schema in data/output/customer_analytics.db.")
        st.dataframe(dao.table_counts(), hide_index=True)
    with right:
        section("Relationships detected automatically", "Found from the data itself, not from file names.")
        for item in str(run.get("detected_relationships", "")).split(" ; "):
            if item:
                st.markdown(f"- `{item}`")

        section("Where to go next")
        st.markdown(
            "- **KPI Dashboard** for segmentation, peak time, merchants, geo consistency and channel mix\n"
            "- **Customer Search** for a single customer's profile, history and alerts\n"
            "- **Anomaly Alerts** for the rule based alert queue\n"
            "- **Data Quality** for the cleaning report and quarantined rows\n\n"
            "The filters in the sidebar apply to the KPI and alert pages."
        )


# ====================================================================== #
# KPI dashboard
# ====================================================================== #
def _kpi_cards(filters: TransactionFilters) -> bool:
    """Top row of KPI cards. Returns False when the filters match nothing."""
    overview = dao.kpi("kpi_overview", filters).iloc[0]
    if not overview["total_transactions"]:
        empty_state()
        return False

    geo = dao.kpi("geo_consistency_overall", filters).iloc[0]
    mix = dao.kpi("digital_vs_branch", filters).iloc[0]

    row1 = st.columns(4)
    with row1[0]:
        kpi_card("Transactions", fmt_number(overview["total_transactions"]),
                 f"{overview['first_date']} to {overview['last_date']}")
    with row1[1]:
        kpi_card("Active customers", fmt_number(overview["active_customers"]),
                 f"{fmt_number(overview['active_merchants'])} merchants used")
    with row1[2]:
        kpi_card("Total value", fmt_compact(overview["total_value"]),
                 f"avg {fmt_number(overview['avg_transaction_value'], 2)} per transaction", tone="navy")
    with row1[3]:
        kpi_card("Flagged transactions", fmt_number(overview["flagged_transactions"]),
                 f"{fmt_number(overview['high_risk_transactions'])} high risk", tone="alert")

    st.write("")
    row2 = st.columns(4)
    with row2[0]:
        kpi_card("Digital share", fmt_pct(overview["digital_share_pct"]),
                 f"digital to branch ratio {fmt_ratio(mix['digital_to_branch_ratio'])}")
    with row2[1]:
        kpi_card("Repeat merchant ratio", fmt_pct(overview["repeat_merchant_ratio_pct"]),
                 "txns at a merchant already used")
    with row2[2]:
        kpi_card("Geo consistency index", fmt_ratio(geo["geo_consistency_index"]),
                 f"{fmt_number(geo['customers_with_history'])} customers with 2+ txns")
    with row2[3]:
        kpi_card("Home location ratio", fmt_pct((geo["home_location_ratio"] or 0) * 100),
                 "txns at the customer's home location", tone="warn")
    return True


def render_kpi_dashboard(filters: TransactionFilters) -> None:
    """KPI cards plus one tab per KPI family."""
    page_header("KPI Dashboard", "Every number on this page is calculated by SQL in SQLite, using the sidebar filters.")
    if not _kpi_cards(filters):
        return

    tabs = st.tabs(["Customer segmentation", "Peak transaction time", "Merchants",
                    "Geo consistency", "Digital vs branch", "Categories"])

    # --- Segmentation -----------------------------------------------------
    with tabs[0]:
        segments = dao.kpi("segmentation_by_segment", filters)
        section("Customer segmentation",
                "Business segments from the customer master, plus value tiers that split active customers "
                "into three equal groups by total spend.")
        c1, c2 = st.columns(2)
        c1.plotly_chart(charts.segment_value_bar(segments), key="seg_value")
        c2.plotly_chart(charts.segment_behaviour_bar(segments), key="seg_behaviour")
        c3, c4 = st.columns([1, 1.3])
        c3.plotly_chart(charts.value_tier_stacked(dao.kpi("value_tier_by_segment", filters)), key="seg_tiers")
        with c4:
            tiers = dao.kpi("customer_value_tiers", filters)
            tier_choice = st.segmented_control("Value tier", ["High Value", "Mid Value", "Low Value"],
                                               default="High Value", key="tier_choice")
            shown = tiers if not tier_choice else tiers[tiers["value_tier"] == tier_choice]
            st.dataframe(shown, hide_index=True, height=290,
                         column_config={"total_spend": st.column_config.NumberColumn(format="%.2f"),
                                        "avg_spend": st.column_config.NumberColumn(format="%.2f")})

    # --- Peak time --------------------------------------------------------
    with tabs[1]:
        hourly = dao.kpi("peak_by_hour", filters)
        buckets = dao.kpi("peak_by_time_bucket", filters)
        weekdays = dao.kpi("peak_by_day_of_week", filters)
        peak_hour = hourly.sort_values("transactions", ascending=False).iloc[0]
        peak_bucket = buckets.sort_values("transactions", ascending=False).iloc[0]
        peak_day = weekdays.sort_values("transactions", ascending=False).iloc[0]
        section("Peak transaction time analysis",
                f"Busiest hour {int(peak_hour['txn_hour']):02d}:00 with {int(peak_hour['transactions'])} transactions. "
                f"Busiest part of day: {peak_bucket['time_bucket']}. Busiest weekday: {peak_day['day_of_week']}.")
        st.plotly_chart(charts.hourly_bar(hourly), key="peak_hour")
        c1, c2 = st.columns([1.6, 1])
        c1.plotly_chart(charts.day_hour_heatmap(dao.kpi("hour_day_heatmap", filters)), key="peak_heat")
        c2.plotly_chart(charts.time_bucket_donut(buckets), key="peak_bucket")
        c3, c4 = st.columns(2)
        c3.plotly_chart(charts.weekday_bar(weekdays), key="peak_weekday")
        c4.plotly_chart(charts.daily_trend_line(dao.kpi("daily_trend", filters)), key="peak_daily")

    # --- Merchants: repeat ratio, risk exposure, category consistency ----
    with tabs[2]:
        overall = dao.kpi("repeat_merchant_overall", filters).iloc[0]
        overview = dao.kpi("kpi_overview", filters).iloc[0]
        section("Repeat merchant ratio",
                "Share of transactions made at a merchant the same customer had already used: "
                "(transactions minus unique customer and merchant pairs) divided by transactions.")
        cols = st.columns(4)
        with cols[0]:
            kpi_card("Repeat merchant ratio", fmt_pct(overall["repeat_merchant_ratio_pct"]),
                     f"{fmt_number(overall['repeat_transactions'])} of {fmt_number(overall['transactions'])} txns")
        with cols[1]:
            kpi_card("Customers with a repeat merchant", fmt_number(overall["customers_with_repeat_merchant"]),
                     tone="navy")
        with cols[2]:
            kpi_card("At High risk merchants", fmt_pct(overview["high_risk_merchant_share_pct"]),
                     "share of transactions", tone="alert")
        with cols[3]:
            kpi_card("Category mismatch", fmt_pct(overview["category_mismatch_pct"]),
                     "booked category differs from the merchant's", tone="warn")
        c1, c2 = st.columns(2)
        c1.plotly_chart(charts.repeat_by_segment_bar(dao.kpi("repeat_merchant_by_segment", filters)), key="rep_seg")
        c2.plotly_chart(charts.top_merchants_bar(dao.kpi("top_merchants", filters)), key="rep_top")

        section("Merchant risk and category consistency",
                "From the merchant master. Risk rating shows how much activity goes to merchants the bank already "
                "rates as risky. Category consistency compares the category booked on each transaction with the "
                "category the merchant is registered under.")
        c3, c4 = st.columns(2)
        c3.plotly_chart(charts.merchant_risk_exposure_bar(dao.kpi("merchant_risk_exposure", filters)), key="mer_risk")
        c4.plotly_chart(charts.merchant_category_heatmap(dao.kpi("merchant_category_consistency", filters)),
                        key="mer_cat")
        st.dataframe(dao.kpi("merchant_category_summary", filters), hide_index=True)

    # --- Geo --------------------------------------------------------------
    with tabs[3]:
        geo_customers = dao.kpi("geo_consistency_by_customer", filters)
        section("Geo-location consistency index",
                "For each customer with two or more transactions, the share of transactions made at their most used "
                "location. 1.0 means the customer always transacts in one place. The index is the average across "
                "customers. Low values mean spread out activity and feed the sudden location change rule.")
        st.dataframe(dao.kpi("geo_consistency_by_segment", filters), hide_index=True)
        c1, c2 = st.columns(2)
        c1.plotly_chart(charts.geo_index_histogram(geo_customers), key="geo_hist")
        c2.plotly_chart(charts.geo_locations_scatter(geo_customers), key="geo_scatter")
        with st.expander("Customer level geo consistency"):
            st.dataframe(geo_customers, hide_index=True)

    # --- Channel mix ------------------------------------------------------
    with tabs[4]:
        mix = dao.kpi("digital_vs_branch", filters).iloc[0]
        section("Digital vs branch transaction mix",
                "Channel usage overall, by segment and over time, plus how often customers use the channel they say "
                "they prefer.")
        cols = st.columns(4)
        with cols[0]:
            kpi_card("Digital", fmt_number(mix["digital_txns"]), fmt_pct(mix["digital_share_pct"]))
        with cols[1]:
            kpi_card("Branch", fmt_number(mix["branch_txns"]), "in person at a branch", tone="navy")
        with cols[2]:
            kpi_card("ATM", fmt_number(mix["atm_txns"]), "self service", tone="warn")
        with cols[3]:
            kpi_card("Digital share of digital + branch", fmt_pct(mix["digital_share_of_digital_branch_pct"]),
                     f"ratio {fmt_ratio(mix['digital_to_branch_ratio'])} digital per branch txn")
        c1, c2 = st.columns([1, 1.4])
        c1.plotly_chart(charts.channel_donut(dao.kpi("channel_mix", filters)), key="ch_donut")
        c2.plotly_chart(charts.channel_by_segment_bar(dao.kpi("channel_mix_by_segment", filters)), key="ch_seg")
        c3, c4 = st.columns(2)
        c3.plotly_chart(charts.channel_by_month_line(dao.kpi("channel_mix_by_month", filters)), key="ch_month")
        c4.plotly_chart(charts.preferred_vs_actual_heatmap(dao.kpi("preferred_vs_actual_channel", filters)), key="ch_pref")

    # --- Categories -------------------------------------------------------
    with tabs[5]:
        section("Spend by category and amount band")
        c1, c2 = st.columns(2)
        c1.plotly_chart(charts.category_bar(dao.kpi("category_spend", filters)), key="cat_bar")
        c2.plotly_chart(charts.amount_band_bar(dao.kpi("amount_band_distribution", filters)), key="cat_band")
        st.dataframe(dao.kpi("category_spend", filters), hide_index=True)


# ====================================================================== #
# Customer search
# ====================================================================== #
def render_customer_search() -> None:
    """Customer 360 view."""
    page_header("Customer Search", "Look up a customer by ID or name to see their profile, full history and alerts.")

    directory = dao.customer_directory()
    search_text = st.text_input("Search by customer ID or name", placeholder="for example C018 or Cohen").strip()
    matches = directory
    if search_text:
        needle = search_text.lower()
        matches = directory[
            directory["customer_id"].str.lower().str.contains(needle, regex=False)
            | directory["customer_name"].str.lower().str.contains(needle, regex=False)
        ]
    if matches.empty:
        st.warning("No customer matches that search.")
        return

    labels = (matches["customer_id"] + "  ·  " + matches["customer_name"] + "  ·  " + matches["segment"]).tolist()
    choice = st.selectbox(f"{len(matches)} matching customer(s)", labels)
    customer_id = choice.split("  ·  ")[0]
    profile = dao.customer_profile(customer_id)

    st.markdown(f"### {profile['customer_name']}")
    st.markdown(
        f'<div class="profile-row"><span><b>ID</b> {profile["customer_id"]}</span>'
        f'<span><b>Segment</b> {profile["segment"]}</span>'
        f'<span><b>Home location</b> {profile["home_location_id"]}</span>'
        f'<span><b>Stated channel</b> {profile["preferred_channel"]}</span>'
        f'<span><b>Most used channel</b> {profile["observed_preferred_channel"] or "n/a"}</span>'
        f'<span><b>Most used location</b> {profile["preferred_location"] or "n/a"}</span>'
        f'<span><b>Favourite category</b> {profile["favourite_category"] or "n/a"}</span></div>',
        unsafe_allow_html=True,
    )

    if not profile["txn_count"]:
        st.info("This customer has no transactions in the loaded period.")
        return

    cols = st.columns(6)
    with cols[0]:
        kpi_card("Transactions", fmt_number(profile["txn_count"]), f"{profile['first_txn_date']} to {profile['last_txn_date']}")
    with cols[1]:
        kpi_card("Total spend", fmt_number(profile["total_spend"], 2), tone="navy")
    with cols[2]:
        kpi_card("Average spend", fmt_number(profile["avg_spend"], 2), f"max {fmt_number(profile['max_spend'], 2)}")
    with cols[3]:
        kpi_card("Geo consistency", fmt_ratio(profile["geo_consistency_index"]),
                 f"{fmt_number(profile['distinct_locations'])} locations")
    with cols[4]:
        kpi_card("Digital share", fmt_pct((profile["digital_share"] or 0) * 100),
                 f"repeat merchant {fmt_pct((profile['repeat_merchant_ratio'] or 0) * 100)}")
    with cols[5]:
        kpi_card("Alerts", fmt_number(profile["alert_count"]), f"{fmt_number(profile['high_alerts'])} high severity",
                 tone="alert" if profile["alert_count"] else "")

    history = dao.customer_transactions(customer_id)
    c1, c2 = st.columns([1.7, 1])
    c1.plotly_chart(charts.customer_timeline(history), key="cust_timeline")
    c2.plotly_chart(charts.customer_category_donut(history), key="cust_category")

    section("Transaction history")
    st.dataframe(history, hide_index=True,
                 column_config={"amount": st.column_config.NumberColumn(format="%.2f"),
                                "is_home_location": st.column_config.CheckboxColumn("Home loc."),
                                "is_repeat_merchant": st.column_config.CheckboxColumn("Repeat merch.")})

    alerts = dao.customer_alerts(customer_id)
    section("Alerts for this customer", "" if not alerts.empty else "No rule fired for this customer.")
    if not alerts.empty:
        st.dataframe(alerts, hide_index=True, column_config={"amount": st.column_config.NumberColumn(format="%.2f")})


# ====================================================================== #
# Anomaly alerts
# ====================================================================== #
def render_alerts(filters: TransactionFilters) -> None:
    """Alert summary and the filterable alert queue."""
    page_header("Anomaly Alerts",
                "Rule based detection only, no machine learning. Each alert states the business reason that fired it, "
                "and severities add up to a risk score per transaction.")

    alerts = dao.kpi("alert_list", filters)
    by_rule = dao.kpi("alerts_by_rule", filters)
    risk = dao.kpi("risk_level_distribution", filters)
    if alerts.empty:
        empty_state("No alerts for the current filters.")
        return

    risk_counts = dict(zip(risk["risk_level"], risk["transactions"]))
    cols = st.columns(4)
    with cols[0]:
        kpi_card("Alerts", fmt_number(len(alerts)), f"{alerts['transaction_id'].nunique()} transactions", tone="alert")
    with cols[1]:
        kpi_card("High risk transactions", fmt_number(risk_counts.get("High", 0)), "risk score 5 or more", tone="alert")
    with cols[2]:
        kpi_card("Medium risk transactions", fmt_number(risk_counts.get("Medium", 0)), "risk score 3 to 4", tone="warn")
    with cols[3]:
        kpi_card("Customers affected", fmt_number(alerts["customer_id"].nunique()),
                 f"value at risk {fmt_compact(alerts.drop_duplicates('transaction_id')['amount'].sum())}", tone="navy")

    c1, c2 = st.columns([1.5, 1])
    c1.plotly_chart(charts.alerts_by_rule_bar(by_rule), key="al_rule")
    c2.plotly_chart(charts.risk_level_bar(risk), key="al_risk")

    section("Alert queue", "Sorted by risk score. Narrow it down with the controls below.")
    f1, f2, f3 = st.columns([1, 1.6, 1])
    severity_pick = f1.multiselect("Severity", ["High", "Medium", "Low"], default=["High", "Medium"])
    rule_pick = f2.multiselect("Rule", sorted(alerts["rule_name"].unique()))
    customer_pick = f3.text_input("Customer ID or name contains").strip().lower()

    queue = alerts.copy()
    if severity_pick:
        queue = queue[queue["severity"].isin(severity_pick)]
    if rule_pick:
        queue = queue[queue["rule_name"].isin(rule_pick)]
    if customer_pick:
        queue = queue[queue["customer_id"].str.lower().str.contains(customer_pick, regex=False)
                      | queue["customer_name"].str.lower().str.contains(customer_pick, regex=False)]

    st.caption(f"{len(queue)} alert(s) shown")
    st.dataframe(
        queue, hide_index=True, height=420,
        column_config={
            "amount": st.column_config.NumberColumn(format="%.2f"),
            "risk_score": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=int(alerts["risk_score"].max()),
                                                          format="%d"),
            "details": st.column_config.TextColumn("Why it fired", width="large"),
        },
    )
    st.download_button("Download shown alerts as CSV", queue.to_csv(index=False).encode("utf-8"),
                       file_name="anomaly_alerts_filtered.csv", mime="text/csv")

    c3, c4 = st.columns([1.2, 1])
    with c3:
        section("Customers with the highest risk")
        st.dataframe(dao.kpi("top_risky_customers", filters), hide_index=True)
    with c4:
        section("Rule catalogue")
        catalogue = dao.rule_catalogue()
        for _, rule in catalogue.iterrows():
            st.markdown(f"{severity_badge(rule['severity'])} **{rule['rule_name']}**  \n"
                        f"<span style='opacity:0.7;font-size:0.85rem'>{rule['description']}</span>",
                        unsafe_allow_html=True)


# ====================================================================== #
# Data quality
# ====================================================================== #
def render_data_quality() -> None:
    """Cleaning report and schema validation."""
    page_header("Data Quality", "What the ingestion and cleaning stages checked, fixed and rejected in the latest run.")
    summary = dao.pipeline_summary()

    section("Schema validation per source file")
    validation = pd.DataFrame(summary.get("schema_validation", []))
    if not validation.empty:
        for column in ("missing_columns", "extra_columns", "type_issues", "pattern_issues"):
            validation[column] = validation[column].astype(str)
        st.dataframe(validation, hide_index=True)

    quality = dao.data_quality_log()
    issues = quality[quality["rows_affected"] > 0]
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Checks performed", fmt_number(len(quality)), "across four tables", tone="navy")
    with c2:
        kpi_card("Checks that found issues", fmt_number(len(issues)), "fixed or quarantined",
                 tone="warn" if len(issues) else "")
    rejected = dao.rejected_records()
    with c3:
        kpi_card("Rejected records", fmt_number(len(rejected)), "see data/processed/rejected_records.csv",
                 tone="alert" if len(rejected) else "")

    section("Checks that found issues")
    if issues.empty:
        st.success("Every check passed on the source files. No rows needed fixing or quarantine.")
    else:
        st.dataframe(issues, hide_index=True)

    with st.expander("All checks performed"):
        st.dataframe(quality, hide_index=True)

    if not rejected.empty:
        section("Quarantined records")
        st.dataframe(rejected, hide_index=True)
