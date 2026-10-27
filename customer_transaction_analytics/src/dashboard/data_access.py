"""
Data access for the dashboard.

KPI numbers come from the shared KPI engine (kpi_queries.sql) so the
dashboard and the batch reports always agree. Look ups that are specific
to the UI (filter options, customer profile, metadata) are small SQL
statements defined here. Every function is cached and the cache is
cleared when the database file changes.
"""

import json
from typing import Dict, Optional, Tuple

import pandas as pd
import streamlit as st

from src.database.db_manager import get_connection, query_to_dataframe
from src.kpi.kpi_engine import KPIEngine
from src.kpi.kpi_queries import TransactionFilters
from src.utils.config import DATABASE_PATH, PROCESSED_DATA_DIR, REPORTS_DIR

# Hashable version of TransactionFilters used as a cache key
FilterKey = Tuple


def database_exists() -> bool:
    """True once the pipeline has created the SQLite file."""
    return DATABASE_PATH.exists()


def database_version() -> float:
    """Modification time of the database, used to invalidate caches after a new run."""
    return DATABASE_PATH.stat().st_mtime if DATABASE_PATH.exists() else 0.0


def filters_to_key(filters: TransactionFilters) -> FilterKey:
    """Convert filters into an immutable tuple for st.cache_data."""
    return (
        filters.start_date, filters.end_date, tuple(filters.segments), tuple(filters.channels),
        tuple(filters.categories), tuple(filters.risk_levels), tuple(filters.merchant_risk_levels),
        filters.customer_id,
    )


def key_to_filters(key: FilterKey) -> TransactionFilters:
    """Rebuild TransactionFilters from its cache key."""
    start, end, segments, channels, categories, risks, merchant_risks, customer = key
    return TransactionFilters(
        start_date=start, end_date=end, segments=list(segments), channels=list(channels),
        categories=list(categories), risk_levels=list(risks),
        merchant_risk_levels=list(merchant_risks), customer_id=customer,
    )


@st.cache_data(show_spinner=False)
def _run_sql(sql: str, params_json: str, db_version: float) -> pd.DataFrame:
    """Cached execution of a plain SQL statement."""
    with get_connection(read_only=True) as connection:
        return query_to_dataframe(connection, sql, json.loads(params_json))


def run_sql(sql: str, params: Optional[dict] = None) -> pd.DataFrame:
    """Run a SQL statement through the cache."""
    return _run_sql(sql, json.dumps(params or {}, sort_keys=True), database_version())


@st.cache_data(show_spinner=False)
def _run_kpi(query_name: str, filter_key: FilterKey, db_version: float) -> pd.DataFrame:
    """Cached KPI query."""
    return KPIEngine().run(query_name, key_to_filters(filter_key))


def kpi(query_name: str, filters: Optional[TransactionFilters] = None) -> pd.DataFrame:
    """Run a named KPI query from kpi_queries.sql with the given filters."""
    return _run_kpi(query_name, filters_to_key(filters or TransactionFilters()), database_version())


# ---------------------------------------------------------------------- #
# UI specific look ups
# ---------------------------------------------------------------------- #
def filter_options() -> Dict[str, object]:
    """Distinct values and the date range for the sidebar filters."""
    dates = run_sql("SELECT MIN(txn_date) AS min_date, MAX(txn_date) AS max_date FROM fact_transaction").iloc[0]
    return {
        "min_date": pd.to_datetime(dates["min_date"]).date(),
        "max_date": pd.to_datetime(dates["max_date"]).date(),
        "segments": run_sql("SELECT DISTINCT segment FROM dim_customer ORDER BY segment")["segment"].tolist(),
        "channels": run_sql("SELECT DISTINCT channel FROM fact_transaction ORDER BY channel")["channel"].tolist(),
        "categories": run_sql("SELECT DISTINCT category FROM fact_transaction ORDER BY category")["category"].tolist(),
        "risk_levels": ["High", "Medium", "Low", "None"],
        "merchant_risk_levels": run_sql(
            """
            SELECT DISTINCT merchant_risk_level FROM dim_merchant
            ORDER BY CASE merchant_risk_level WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END
            """
        )["merchant_risk_level"].tolist(),
    }


def customer_directory() -> pd.DataFrame:
    """Every customer with a few columns for the search box."""
    return run_sql(
        """
        SELECT customer_id, customer_name, segment, txn_count, total_spend, alert_count
        FROM vw_customer_360
        ORDER BY customer_id
        """
    )


def customer_profile(customer_id: str) -> pd.Series:
    """Full customer 360 row."""
    frame = run_sql("SELECT * FROM vw_customer_360 WHERE customer_id = :cid", {"cid": customer_id})
    return frame.iloc[0] if not frame.empty else pd.Series(dtype=object)


def customer_transactions(customer_id: str) -> pd.DataFrame:
    """All transactions of one customer, newest first."""
    return run_sql(
        """
        SELECT transaction_id, txn_datetime, amount, category, channel, merchant_id, merchant_name,
               merchant_risk_level, location_id,
               is_home_location, is_repeat_merchant, time_bucket, risk_score, risk_level, rule_codes
        FROM vw_transaction_details
        WHERE customer_id = :cid
        ORDER BY txn_datetime DESC
        """,
        {"cid": customer_id},
    )


def customer_alerts(customer_id: str) -> pd.DataFrame:
    """All alerts raised for one customer."""
    return run_sql(
        """
        SELECT alert_id, txn_datetime, transaction_id, rule_name, severity, amount, merchant_name, details
        FROM vw_alert_details
        WHERE customer_id = :cid
        ORDER BY txn_datetime DESC, severity_weight DESC
        """,
        {"cid": customer_id},
    )


def rule_catalogue() -> pd.DataFrame:
    """Rules used by the anomaly engine."""
    return run_sql("SELECT rule_code, rule_name, severity, severity_weight, description FROM anomaly_rule ORDER BY rule_code")


def latest_pipeline_run() -> pd.Series:
    """Most recent pipeline run."""
    frame = run_sql("SELECT * FROM pipeline_run ORDER BY started_at DESC LIMIT 1")
    return frame.iloc[0] if not frame.empty else pd.Series(dtype=object)


def data_quality_log() -> pd.DataFrame:
    """Data quality checks of the latest run."""
    return run_sql(
        """
        SELECT table_name, check_name, rows_affected, action
        FROM data_quality_log
        WHERE run_id = (SELECT run_id FROM pipeline_run ORDER BY started_at DESC LIMIT 1)
        ORDER BY log_id
        """
    )


def table_counts() -> pd.DataFrame:
    """Row counts for the main database tables."""
    tables = ["fact_transaction", "dim_customer", "dim_merchant", "dim_time", "dim_location",
              "anomaly_alert", "transaction_risk", "anomaly_rule"]
    union = " UNION ALL ".join(f"SELECT '{t}' AS table_name, COUNT(*) AS rows FROM {t}" for t in tables)
    return run_sql(union)


def rejected_records() -> pd.DataFrame:
    """Quarantined rows written by the cleaning stage."""
    path = PROCESSED_DATA_DIR / "rejected_records.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def pipeline_summary() -> dict:
    """Schema validation and stage timings from the last run."""
    path = REPORTS_DIR / "pipeline_summary.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
