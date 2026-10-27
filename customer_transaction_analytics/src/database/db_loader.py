"""
Load curated data into SQLite.

Steps
1. Rebuild the schema from schema.sql (idempotent full refresh).
2. Map the Pandas column names to the database column names.
3. Insert dimensions first, then the fact table, then analytics tables, so
   every foreign key already exists when a child row arrives.
4. Create the reporting views from views.sql.
"""

import sqlite3
from typing import Dict, List

import pandas as pd

from src.database.db_manager import execute_sql_file, get_connection, table_row_counts
from src.preprocessing.cleaning_report import CleaningReport
from src.utils.config import DATABASE_PATH, SCHEMA_SQL_PATH, VIEWS_SQL_PATH
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Pandas column -> database column, per target table
CUSTOMER_COLUMN_MAP = {
    "CustomerID": "customer_id",
    "CustomerName": "customer_name",
    "Segment": "segment",
    "HomeLocationID": "home_location_id",
    "PreferredChannel": "preferred_channel",
}

TIME_COLUMN_MAP = {
    "TimeID": "time_id",
    "Date": "txn_date",
    "DayOfWeek": "day_of_week",
    "Month": "month",
    "Year": "year",
    "HourOfDay": "hour_of_day",
}

FACT_COLUMN_MAP = {
    "TransactionID": "transaction_id",
    "CustomerID": "customer_id",
    "MerchantID": "merchant_id",
    "TimeID": "time_id",
    "LocationID": "location_id",
    "Amount": "amount",
    "Category": "category",
    "Channel": "channel",
}


def _table_columns(connection: sqlite3.Connection, table: str) -> List[str]:
    """Column names of a table, read from the database itself."""
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()]


def _insert(connection: sqlite3.Connection, table: str, frame: pd.DataFrame) -> int:
    """
    Append a DataFrame to an existing table.

    Only columns that exist in the table are written, which keeps the
    database schema (not Pandas) in charge of the structure.
    """
    columns = [col for col in _table_columns(connection, table) if col in frame.columns]
    to_write = frame[columns].copy()

    # SQLite has no datetime type: store ISO strings
    for column in to_write.columns:
        if pd.api.types.is_datetime64_any_dtype(to_write[column]):
            fmt = "%Y-%m-%d %H:%M:%S" if column.endswith("datetime") else "%Y-%m-%d"
            to_write[column] = to_write[column].dt.strftime(fmt)

    to_write = to_write.astype(object).where(to_write.notna(), None)
    to_write.to_sql(table, connection, if_exists="append", index=False)
    return len(to_write)


def prepare_tables(
    cleaned: Dict[str, pd.DataFrame], features: Dict[str, pd.DataFrame], anomalies: Dict[str, pd.DataFrame]
) -> Dict[str, pd.DataFrame]:
    """Build one DataFrame per database table with database column names."""
    customer_dim = features["customer_features"].rename(columns=CUSTOMER_COLUMN_MAP)

    time_dim = cleaned["time"].rename(columns=TIME_COLUMN_MAP)

    fact = features["transaction_features"].rename(columns=FACT_COLUMN_MAP)

    alerts = anomalies["alerts"].rename(columns={"TransactionID": "transaction_id", "CustomerID": "customer_id"})
    risk = anomalies["transaction_risk"].rename(columns={"TransactionID": "transaction_id", "CustomerID": "customer_id"})

    return {
        "dim_location": features["location_dim"],
        "dim_customer": customer_dim,
        "dim_time": time_dim,
        "dim_merchant": features["merchant_dim"],
        "fact_transaction": fact,
        "anomaly_rule": anomalies["rules"],
        "anomaly_alert": alerts,
        "transaction_risk": risk,
    }


# Insert order respects foreign keys
LOAD_ORDER = [
    "dim_location", "dim_customer", "dim_time", "dim_merchant",
    "fact_transaction", "anomaly_rule", "anomaly_alert", "transaction_risk",
]


def load_to_sqlite(
    cleaned: Dict[str, pd.DataFrame],
    features: Dict[str, pd.DataFrame],
    anomalies: Dict[str, pd.DataFrame],
    db_path=DATABASE_PATH,
) -> pd.DataFrame:
    """
    Full refresh of the SQLite database.

    Returns:
        DataFrame with the row count of every table after the load.
    """
    tables = prepare_tables(cleaned, features, anomalies)

    with get_connection(db_path) as connection:
        execute_sql_file(connection, SCHEMA_SQL_PATH)
        for table in LOAD_ORDER:
            written = _insert(connection, table, tables[table])
            logger.info("Loaded %-18s %5d rows", table, written)
        execute_sql_file(connection, VIEWS_SQL_PATH)

        violations = connection.execute("PRAGMA foreign_key_check;").fetchall()
        if violations:
            raise RuntimeError(f"Foreign key violations after load: {violations[:5]}")
        counts = table_row_counts(connection)

    logger.info("SQLite database ready at %s", db_path)
    return counts


def record_pipeline_run(run_info: dict, report: CleaningReport, db_path=DATABASE_PATH) -> None:
    """Store run metadata and every data quality check in the database."""
    with get_connection(db_path) as connection:
        pd.DataFrame([run_info]).to_sql("pipeline_run", connection, if_exists="append", index=False)
        quality = report.steps_frame.rename(columns={"table": "table_name", "check": "check_name"})
        quality.insert(0, "run_id", run_info["run_id"])
        quality.to_sql("data_quality_log", connection, if_exists="append", index=False)
