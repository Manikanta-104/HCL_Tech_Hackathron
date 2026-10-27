"""
KPI engine.

Runs the SQL KPI library against SQLite. Used in two places:
    - the batch pipeline (main.py) to export every KPI to data/output and
      write reports/kpi_report.md
    - the Streamlit dashboard, with the sidebar filters applied
"""

from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from src.database.db_manager import get_connection, query_to_dataframe
from src.kpi.kpi_queries import TransactionFilters, compose_query, load_query_library
from src.utils.config import DATABASE_PATH, OUTPUT_DATA_DIR, REPORTS_DIR
from src.utils.helpers import dataframe_to_markdown
from src.utils.logger import get_logger

logger = get_logger(__name__)


class KPIEngine:
    """Executes named KPI queries with optional filters."""

    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = db_path
        self.queries = load_query_library()

    def available_kpis(self) -> list:
        """Names of every query in the library."""
        return list(self.queries.keys())

    def run(self, query_name: str, filters: Optional[TransactionFilters] = None) -> pd.DataFrame:
        """
        Run one KPI query.

        Args:
            query_name: Key from kpi_queries.sql (the '-- name:' value).
            filters: Optional filters applied through the 'ft' CTE.

        Returns:
            Query result as a DataFrame.
        """
        if query_name not in self.queries:
            raise KeyError(f"Unknown KPI query '{query_name}'. Available: {self.available_kpis()}")
        sql, params = compose_query(self.queries[query_name], filters)
        with get_connection(self.db_path, read_only=True) as connection:
            return query_to_dataframe(connection, sql, params)

    def run_all(self, filters: Optional[TransactionFilters] = None) -> Dict[str, pd.DataFrame]:
        """Run every query in the library."""
        return {name: self.run(name, filters) for name in self.queries}


# ---------------------------------------------------------------------- #
# Batch outputs
# ---------------------------------------------------------------------- #
def export_kpis(results: Dict[str, pd.DataFrame], output_dir: Path = OUTPUT_DATA_DIR) -> None:
    """Write every KPI result to data/output/kpi_<name>.csv."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in results.items():
        frame.to_csv(output_dir / f"kpi_{name}.csv", index=False)
    logger.info("Exported %d KPI result sets to %s", len(results), output_dir)


def write_kpi_report(results: Dict[str, pd.DataFrame], reports_dir: Path = REPORTS_DIR) -> Path:
    """Write a readable Markdown summary of the main KPIs."""
    overview = results["kpi_overview"].iloc[0]
    geo = results["geo_consistency_overall"].iloc[0]
    repeat = results["repeat_merchant_overall"].iloc[0]
    mix = results["digital_vs_branch"].iloc[0]
    peak_hour = results["peak_by_hour"].sort_values("transactions", ascending=False).iloc[0]
    peak_bucket = results["peak_by_time_bucket"].sort_values("transactions", ascending=False).iloc[0]
    peak_day = results["peak_by_day_of_week"].sort_values("transactions", ascending=False).iloc[0]

    lines = [
        "# KPI Report",
        "",
        f"Period covered: {overview['first_date']} to {overview['last_date']}",
        "",
        "## Headline numbers",
        "",
        "| KPI | Value |",
        "| --- | --- |",
        f"| Transactions | {int(overview['total_transactions']):,} |",
        f"| Active customers | {int(overview['active_customers']):,} |",
        f"| Active merchants | {int(overview['active_merchants']):,} |",
        f"| Total value | {overview['total_value']:,.2f} |",
        f"| Average transaction value | {overview['avg_transaction_value']:,.2f} |",
        f"| Digital share of transactions | {overview['digital_share_pct']:.2f}% |",
        f"| Repeat merchant ratio | {repeat['repeat_merchant_ratio_pct']:.2f}% |",
        f"| Geo-location consistency index | {geo['geo_consistency_index']:.4f} |",
        f"| Digital to branch ratio | {mix['digital_to_branch_ratio']:.2f} |",
        f"| Share of transactions at High risk merchants | {overview['high_risk_merchant_share_pct']:.2f}% |",
        f"| Transactions with a category mismatch | {overview['category_mismatch_pct']:.2f}% |",
        f"| Flagged transactions | {int(overview['flagged_transactions'])} |",
        f"| High risk transactions | {int(overview['high_risk_transactions'])} |",
        "",
        "## 1. Customer segmentation",
        "",
        dataframe_to_markdown(results["segmentation_by_segment"]),
        "Value tiers (NTILE on total spend) by segment:",
        "",
        dataframe_to_markdown(results["value_tier_by_segment"]),
        "## 2. Peak transaction time",
        "",
        f"Busiest hour: {int(peak_hour['txn_hour']):02d}:00 ({int(peak_hour['transactions'])} transactions). "
        f"Busiest part of day: {peak_bucket['time_bucket']}. Busiest weekday: {peak_day['day_of_week']}.",
        "",
        dataframe_to_markdown(results["peak_by_time_bucket"]),
        dataframe_to_markdown(results["peak_by_day_of_week"]),
        "## 3. Repeat merchant ratio",
        "",
        dataframe_to_markdown(results["repeat_merchant_overall"]),
        dataframe_to_markdown(results["repeat_merchant_by_segment"]),
        "Top merchants:",
        "",
        dataframe_to_markdown(results["top_merchants"]),
        "## 4. Geo-location consistency index",
        "",
        "Average share of a customer's transactions made at their most used location "
        "(customers with two or more transactions).",
        "",
        dataframe_to_markdown(results["geo_consistency_overall"]),
        dataframe_to_markdown(results["geo_consistency_by_segment"]),
        "## 5. Digital vs branch transaction mix",
        "",
        dataframe_to_markdown(results["channel_mix"]),
        dataframe_to_markdown(results["digital_vs_branch"]),
        dataframe_to_markdown(results["channel_mix_by_segment"]),
        "## Merchant risk and category consistency",
        "",
        "Activity by the merchant's risk rating in the merchant master:",
        "",
        dataframe_to_markdown(results["merchant_risk_exposure"]),
        "Registered merchant category against the category booked on the transaction:",
        "",
        dataframe_to_markdown(results["merchant_category_summary"]),
        "## Category spend",
        "",
        dataframe_to_markdown(results["category_spend"]),
    ]
    path = reports_dir / "kpi_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("KPI report written to %s", path)
    return path


def write_anomaly_report(results: Dict[str, pd.DataFrame], reports_dir: Path = REPORTS_DIR) -> Path:
    """Write a Markdown summary of the rule based alerts."""
    alerts = results["alert_list"]
    lines = [
        "# Anomaly Detection Report",
        "",
        "Rule based detection only. Each alert carries the business reason that triggered it.",
        "",
        f"Total alerts: {len(alerts)} on {alerts['transaction_id'].nunique() if not alerts.empty else 0} transactions.",
        "",
        "## Alerts by rule",
        "",
        dataframe_to_markdown(results["alerts_by_rule"]),
        "## Risk level distribution",
        "",
        dataframe_to_markdown(results["risk_level_distribution"]),
        "## Customers with the highest risk",
        "",
        dataframe_to_markdown(results["top_risky_customers"]),
        "## Highest priority alerts",
        "",
        dataframe_to_markdown(
            alerts[["alert_id", "txn_datetime", "transaction_id", "customer_id", "rule_name",
                    "severity", "amount", "risk_level", "details"]],
            max_rows=25,
        ),
    ]
    path = reports_dir / "anomaly_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Anomaly report written to %s", path)
    return path
