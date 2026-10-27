"""
Data cleaning and validation.

Cleaning order matters: dimensions (customers, merchants, time) are cleaned first so
that transactions can then be checked for referential integrity against the
cleaned dimension keys.

Rule of thumb used throughout
    - Repair what can be repaired safely (whitespace, casing, synonyms,
      derived calendar fields).
    - Fill non critical gaps with an explicit "Unknown" label.
    - Quarantine rows whose key facts are missing or wrong (IDs, amount,
      date, hour) because they would corrupt KPIs.
"""

from typing import Dict, Iterable, Optional, Tuple

import numpy as np
import pandas as pd

from src.ingestion.schema_registry import (
    CUSTOMERS_SCHEMA,
    MERCHANTS_SCHEMA,
    TIME_SCHEMA,
    TRANSACTIONS_SCHEMA,
    TableSchema,
)
from src.preprocessing.cleaning_report import CleaningReport
from src.utils.config import (
    CHANNEL_SYNONYMS,
    MAX_VALID_TRANSACTION_AMOUNT,
    NULL_TOKENS,
    UNCATEGORIZED_LABEL,
    UNKNOWN_LABEL,
    VALID_CHANNELS,
    VALID_MERCHANT_RISK_LEVELS,
    VALID_SEGMENTS,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ====================================================================== #
# Generic, reusable cleaning steps
# ====================================================================== #
def standardize_text(frame: pd.DataFrame, table: str, report: CleaningReport) -> pd.DataFrame:
    """Trim whitespace in every text cell and turn null like tokens into NaN."""
    cleaned = frame.copy()
    changed_cells = 0
    null_tokens = {token.lower() for token in NULL_TOKENS}

    for column in cleaned.columns:
        original = cleaned[column]
        stripped = original.astype("string").str.strip()
        is_null_token = stripped.str.lower().isin(null_tokens)
        stripped = stripped.mask(is_null_token)
        changed_cells += int(((original.astype("string") != stripped) & original.notna()).fillna(False).sum())
        # Back to plain object dtype so downstream code behaves the same on pandas 2 and 3
        cleaned[column] = stripped.astype(object).where(stripped.notna(), np.nan)

    report.log_step(table, "Whitespace and null token standardisation", changed_cells, "cells trimmed or set to null")
    return cleaned


def remove_exact_duplicates(frame: pd.DataFrame, table: str, report: CleaningReport) -> pd.DataFrame:
    """Drop rows that are identical in every column."""
    duplicate_mask = frame.duplicated(keep="first")
    report.log_step(table, "Exact duplicate rows", int(duplicate_mask.sum()), "removed (first copy kept)")
    return frame.loc[~duplicate_mask].reset_index(drop=True)


def remove_duplicate_keys(frame: pd.DataFrame, schema: TableSchema, report: CleaningReport) -> pd.DataFrame:
    """Keep the first row for each primary key and quarantine the rest."""
    key = schema.primary_key
    duplicate_mask = frame[key].notna() & frame.duplicated(subset=[key], keep="first")
    report.reject(schema.name, frame.loc[duplicate_mask], key, f"Duplicate {key}")
    report.log_step(schema.name, f"Duplicate primary key ({key})", int(duplicate_mask.sum()), "quarantined")
    return frame.loc[~duplicate_mask].reset_index(drop=True)


def drop_missing_required(frame: pd.DataFrame, schema: TableSchema, report: CleaningReport) -> pd.DataFrame:
    """Quarantine rows where any mandatory column is empty (for example a null CustomerID)."""
    keep_mask = pd.Series(True, index=frame.index)
    for column in schema.required_columns:
        missing = frame[column].isna()
        report.reject(schema.name, frame.loc[missing & keep_mask], schema.primary_key, f"Missing {column}")
        report.log_step(schema.name, f"Null check on required column {column}", int((missing & keep_mask).sum()), "quarantined")
        keep_mask &= ~missing
    return frame.loc[keep_mask].reset_index(drop=True)


def validate_id_columns(
    frame: pd.DataFrame, schema: TableSchema, report: CleaningReport, required_ids: Iterable[str]
) -> pd.DataFrame:
    """
    Check every ID against its pattern.

    Required IDs with a bad format are quarantined. Optional IDs with a bad
    format are blanked so they show up as Unknown later.
    """
    cleaned = frame.copy()
    required_ids = set(required_ids)
    for column, pattern in schema.id_patterns.items():
        if column not in cleaned.columns:
            continue
        cleaned[column] = cleaned[column].where(cleaned[column].isna(), cleaned[column].astype(str).str.upper())
        bad = cleaned[column].notna() & ~cleaned[column].astype(str).str.match(pattern)
        if column in required_ids:
            report.reject(schema.name, cleaned.loc[bad], schema.primary_key, f"Invalid {column} format")
            report.log_step(schema.name, f"ID format check on {column}", int(bad.sum()), "quarantined")
            cleaned = cleaned.loc[~bad]
        else:
            report.log_step(schema.name, f"ID format check on {column}", int(bad.sum()), "set to null")
            cleaned.loc[bad, column] = np.nan
    return cleaned.reset_index(drop=True)


def normalize_category(
    series: pd.Series,
    allowed: Optional[Iterable[str]] = None,
    synonyms: Optional[Dict[str, str]] = None,
    fill_label: str = UNKNOWN_LABEL,
) -> Tuple[pd.Series, int, int]:
    """
    Normalise a categorical column.

    Steps: map known synonyms, apply title case (ATM stays upper case),
    replace values outside the allowed list and fill blanks.

    Returns:
        (cleaned series, number of blanks filled, number of invalid values replaced)
    """
    synonyms = synonyms or {}
    lowered = series.astype("string").str.lower()
    mapped = lowered.map(lambda v: synonyms.get(v, v) if pd.notna(v) else v)
    titled = mapped.map(lambda v: v if pd.isna(v) or v in synonyms.values() else str(v).title())
    titled = titled.replace({"Atm": "ATM"})

    blanks = int(titled.isna().sum())
    invalid = 0
    if allowed is not None:
        invalid_mask = titled.notna() & ~titled.isin(list(allowed))
        invalid = int(invalid_mask.sum())
        titled = titled.mask(invalid_mask, fill_label)
    return titled.fillna(fill_label).astype(object), blanks, invalid


def parse_amount(series: pd.Series) -> pd.Series:
    """Convert amount text such as 'INR 1,200.50' or '$75' into floats."""
    as_text = series.astype("string").str.replace(r"[^\d.\-]", "", regex=True)
    return pd.to_numeric(as_text, errors="coerce").astype(float)


# ====================================================================== #
# Table specific cleaning
# ====================================================================== #
def clean_customers(raw: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    """Clean the customer master table."""
    schema = CUSTOMERS_SCHEMA
    rows_in = len(raw)

    frame = standardize_text(raw, schema.name, report)
    frame = remove_exact_duplicates(frame, schema.name, report)
    frame = drop_missing_required(frame, schema, report)
    frame = validate_id_columns(frame, schema, report, required_ids=["CustomerID"])
    frame = remove_duplicate_keys(frame, schema, report)

    missing_names = frame["CustomerName"].isna()
    frame["CustomerName"] = frame["CustomerName"].fillna("Unknown Customer")
    report.log_step(schema.name, "Missing CustomerName", int(missing_names.sum()), "filled with 'Unknown Customer'")

    frame["Segment"], blanks, invalid = normalize_category(frame["Segment"], allowed=VALID_SEGMENTS)
    report.log_step(schema.name, "Missing Segment", blanks, f"filled with '{UNKNOWN_LABEL}'")
    report.log_step(schema.name, "Invalid Segment value", invalid, f"replaced with '{UNKNOWN_LABEL}'")

    frame["PreferredChannel"], blanks, invalid = normalize_category(
        frame["PreferredChannel"], allowed=VALID_CHANNELS, synonyms=CHANNEL_SYNONYMS
    )
    report.log_step(schema.name, "Missing PreferredChannel", blanks, f"filled with '{UNKNOWN_LABEL}'")
    report.log_step(schema.name, "Invalid PreferredChannel value", invalid, f"replaced with '{UNKNOWN_LABEL}'")

    missing_home = frame["HomeLocationID"].isna()
    frame["HomeLocationID"] = frame["HomeLocationID"].fillna(UNKNOWN_LABEL)
    report.log_step(schema.name, "Missing HomeLocationID", int(missing_home.sum()), f"filled with '{UNKNOWN_LABEL}'")

    report.set_row_counts(schema.name, rows_in, len(frame))
    return frame[schema.column_names].reset_index(drop=True)


def clean_merchants(raw: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    """Clean the merchant master table."""
    schema = MERCHANTS_SCHEMA
    rows_in = len(raw)

    frame = standardize_text(raw, schema.name, report)
    frame = remove_exact_duplicates(frame, schema.name, report)
    frame = drop_missing_required(frame, schema, report)
    frame = validate_id_columns(frame, schema, report, required_ids=["MerchantID"])
    frame = remove_duplicate_keys(frame, schema, report)

    missing_names = frame["MerchantName"].isna()
    frame["MerchantName"] = frame["MerchantName"].fillna("Unknown Merchant")
    report.log_step(schema.name, "Missing MerchantName", int(missing_names.sum()), "filled with 'Unknown Merchant'")

    frame["MerchantCategory"], blanks, _ = normalize_category(frame["MerchantCategory"], fill_label=UNCATEGORIZED_LABEL)
    report.log_step(schema.name, "Missing MerchantCategory", blanks, f"filled with '{UNCATEGORIZED_LABEL}'")

    # An unknown risk level is treated as risky downstream, never as safe
    frame["RiskLevel"], blanks, invalid = normalize_category(frame["RiskLevel"], allowed=VALID_MERCHANT_RISK_LEVELS)
    report.log_step(schema.name, "Missing merchant RiskLevel", blanks, f"filled with '{UNKNOWN_LABEL}'")
    report.log_step(schema.name, "Invalid merchant RiskLevel value", invalid, f"replaced with '{UNKNOWN_LABEL}'")

    report.set_row_counts(schema.name, rows_in, len(frame))
    return frame[schema.column_names].reset_index(drop=True)


def clean_time(raw: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    """Clean the time dimension and re-derive calendar fields from the date."""
    schema = TIME_SCHEMA
    rows_in = len(raw)

    frame = standardize_text(raw, schema.name, report)
    frame = remove_exact_duplicates(frame, schema.name, report)
    frame = drop_missing_required(frame, schema, report)
    frame = validate_id_columns(frame, schema, report, required_ids=["TimeID"])
    frame = remove_duplicate_keys(frame, schema, report)

    # Date conversion
    parsed_dates = pd.to_datetime(frame["Date"], errors="coerce", format="mixed")
    bad_dates = parsed_dates.isna()
    report.reject(schema.name, frame.loc[bad_dates], schema.primary_key, "Unparseable Date")
    report.log_step(schema.name, "Date conversion", int(bad_dates.sum()), "unparseable dates quarantined")
    frame = frame.loc[~bad_dates].copy()
    frame["Date"] = parsed_dates.loc[~bad_dates].dt.normalize()

    # Hour must be a whole number between 0 and 23
    hours = pd.to_numeric(frame["HourOfDay"], errors="coerce")
    bad_hours = hours.isna() | (hours % 1 != 0) | ~hours.between(0, 23)
    report.reject(schema.name, frame.loc[bad_hours], schema.primary_key, "HourOfDay outside 0-23")
    report.log_step(schema.name, "HourOfDay range check (0-23)", int(bad_hours.sum()), "quarantined")
    frame = frame.loc[~bad_hours].copy()
    frame["HourOfDay"] = hours.loc[~bad_hours].astype(int)

    # Calendar fields are derived from the date, the date is the source of truth
    derived = {
        "DayOfWeek": frame["Date"].dt.day_name(),
        "Month": frame["Date"].dt.strftime("%b"),
        "Year": frame["Date"].dt.year.astype(int),
    }
    for column, true_values in derived.items():
        current = frame[column].astype(str) if column != "Year" else pd.to_numeric(frame[column], errors="coerce")
        mismatched = int((current.values != true_values.values).sum())
        report.log_step(schema.name, f"{column} consistency with Date", mismatched, "re-derived from Date")
        frame[column] = true_values

    report.set_row_counts(schema.name, rows_in, len(frame))
    return frame[schema.column_names].reset_index(drop=True)


def clean_transactions(
    raw: pd.DataFrame,
    customers: pd.DataFrame,
    merchants: pd.DataFrame,
    time_dim: pd.DataFrame,
    report: CleaningReport,
) -> pd.DataFrame:
    """Clean transactions and enforce referential integrity against the dimensions."""
    schema = TRANSACTIONS_SCHEMA
    rows_in = len(raw)

    frame = standardize_text(raw, schema.name, report)
    frame = remove_exact_duplicates(frame, schema.name, report)
    frame = drop_missing_required(frame, schema, report)
    frame = validate_id_columns(frame, schema, report, required_ids=["TransactionID", "CustomerID", "TimeID"])
    frame = remove_duplicate_keys(frame, schema, report)

    # Amount: numeric, positive and within a sane upper bound
    amounts = parse_amount(frame["Amount"])
    not_numeric = amounts.isna()
    report.reject(schema.name, frame.loc[not_numeric], schema.primary_key, "Amount not numeric")
    report.log_step(schema.name, "Amount data type check", int(not_numeric.sum()), "quarantined")

    non_positive = amounts.notna() & (amounts <= 0)
    report.reject(schema.name, frame.loc[non_positive], schema.primary_key, "Amount zero or negative")
    report.log_step(schema.name, "Amount must be positive", int(non_positive.sum()), "quarantined")

    too_large = amounts > MAX_VALID_TRANSACTION_AMOUNT
    report.reject(schema.name, frame.loc[too_large], schema.primary_key, "Amount above sanity limit")
    report.log_step(schema.name, f"Amount above {MAX_VALID_TRANSACTION_AMOUNT:,}", int(too_large.sum()), "quarantined")

    valid_amount = ~(not_numeric | non_positive | too_large)
    frame = frame.loc[valid_amount].copy()
    frame["Amount"] = amounts.loc[valid_amount].round(2)

    # Categorical fields
    frame["Category"], blanks, _ = normalize_category(frame["Category"], fill_label=UNCATEGORIZED_LABEL)
    report.log_step(schema.name, "Missing Category", blanks, f"filled with '{UNCATEGORIZED_LABEL}'")

    frame["Channel"], blanks, invalid = normalize_category(
        frame["Channel"], allowed=VALID_CHANNELS, synonyms=CHANNEL_SYNONYMS
    )
    report.log_step(schema.name, "Missing Channel", blanks, f"filled with '{UNKNOWN_LABEL}'")
    report.log_step(schema.name, "Invalid Channel value", invalid, f"replaced with '{UNKNOWN_LABEL}'")

    for optional_id in ("MerchantID", "LocationID"):
        missing = frame[optional_id].isna()
        frame[optional_id] = frame[optional_id].fillna(UNKNOWN_LABEL)
        report.log_step(schema.name, f"Missing {optional_id}", int(missing.sum()), f"filled with '{UNKNOWN_LABEL}'")

    # Referential integrity against the cleaned dimensions
    orphan_customer = ~frame["CustomerID"].isin(customers["CustomerID"])
    report.reject(schema.name, frame.loc[orphan_customer], schema.primary_key, "CustomerID not in customer master")
    report.log_step(schema.name, "Referential integrity: CustomerID", int(orphan_customer.sum()), "quarantined")
    frame = frame.loc[~orphan_customer]

    # A merchant missing from the master does not make the payment invalid, so
    # the row is kept and the merchant is flagged as unregistered (and alerted on)
    unregistered = ~frame["MerchantID"].isin(merchants["MerchantID"])
    report.log_step(schema.name, "Referential integrity: MerchantID", int(unregistered.sum()),
                    "kept, merchant marked as unregistered")

    orphan_time = ~frame["TimeID"].isin(time_dim["TimeID"])
    report.reject(schema.name, frame.loc[orphan_time], schema.primary_key, "TimeID not in time dimension")
    report.log_step(schema.name, "Referential integrity: TimeID", int(orphan_time.sum()), "quarantined")
    frame = frame.loc[~orphan_time]

    report.set_row_counts(schema.name, rows_in, len(frame))
    return frame[schema.column_names].reset_index(drop=True)


def clean_all_tables(raw_tables: Dict[str, pd.DataFrame]) -> Tuple[Dict[str, pd.DataFrame], CleaningReport]:
    """
    Clean every source table in dependency order.

    Args:
        raw_tables: Output of the ingestion stage keyed by table name.

    Returns:
        (dictionary of cleaned tables, populated CleaningReport)
    """
    report = CleaningReport()
    customers = clean_customers(raw_tables["customers"], report)
    merchants = clean_merchants(raw_tables["merchants"], report)
    time_dim = clean_time(raw_tables["time"], report)
    transactions = clean_transactions(raw_tables["transactions"], customers, merchants, time_dim, report)

    logger.info(
        "Cleaning complete. customers=%d, merchants=%d, time=%d, transactions=%d, rejected=%d",
        len(customers), len(merchants), len(time_dim), len(transactions), len(report.rejected_records),
    )
    cleaned = {"customers": customers, "merchants": merchants, "time": time_dim, "transactions": transactions}
    return cleaned, report
