"""
Feature engineering.

Input : the merged transaction dataset (one row per transaction with
        customer, merchant and time attributes already joined).
Output: 1. transaction level features (time, amount, merchant, geo, channel,
           customer history)
        2. customer level profile (total spend, average spend, preferred
           channel and location, and more)
        3. merchant and location level summaries for the dimension tables

All history based features are computed in time order per customer and only
look backwards, so a transaction never "sees" its own future. This keeps the
anomaly rules honest.
"""

from typing import Dict

import numpy as np
import pandas as pd

from src.utils.config import (
    AMOUNT_BAND_EDGES,
    AMOUNT_BAND_LABELS,
    DIGITAL_CHANNELS,
    TIME_BUCKETS,
    UNKNOWN_LABEL,
    UNREGISTERED_MERCHANT_LABEL,
)
from src.utils.helpers import mode_with_tiebreak
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ====================================================================== #
# Transaction level features
# ====================================================================== #
def _hour_to_bucket(hour: int) -> str:
    """Map an hour of day to its time bucket label."""
    for label, (start, end) in TIME_BUCKETS.items():
        if start <= hour <= end:
            return label
    return UNKNOWN_LABEL


def add_merchant_master_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Attributes that come from the merchant master.

        MerchantRiskLevel       the merchant's risk rating (renamed from RiskLevel so it
                                is never confused with the transaction risk level)
        is_registered_merchant  1 when the merchant exists in the merchant master
        is_high_risk_merchant   1 when the merchant is rated High
        is_category_mismatch    1 when the transaction category differs from the
                                category the merchant is registered under
    """
    df = df.rename(columns={"RiskLevel": "MerchantRiskLevel"}).copy()
    df["is_registered_merchant"] = df["MerchantName"].notna().astype(int)
    df["MerchantName"] = df["MerchantName"].fillna(UNREGISTERED_MERCHANT_LABEL)
    df["MerchantCategory"] = df["MerchantCategory"].fillna(UNKNOWN_LABEL)
    df["MerchantRiskLevel"] = df["MerchantRiskLevel"].fillna(UNKNOWN_LABEL)
    df["is_high_risk_merchant"] = (df["MerchantRiskLevel"] == "High").astype(int)
    df["is_category_mismatch"] = (
        (df["is_registered_merchant"] == 1) & (df["Category"] != df["MerchantCategory"])
    ).astype(int)
    return df


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Transaction hour, day of week, month, weekend flag and part of day."""
    df = df.copy()
    df["txn_date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df["txn_datetime"] = df["txn_date"] + pd.to_timedelta(df["HourOfDay"].astype(int), unit="h")
    df["txn_hour"] = df["HourOfDay"].astype(int)
    df["day_of_week"] = df["txn_date"].dt.day_name()
    df["day_of_week_num"] = df["txn_date"].dt.dayofweek + 1  # Monday = 1
    df["month"] = df["txn_date"].dt.strftime("%b")
    df["month_num"] = df["txn_date"].dt.month
    df["year"] = df["txn_date"].dt.year
    df["year_month"] = df["txn_date"].dt.strftime("%Y-%m")
    df["is_weekend"] = df["day_of_week_num"].isin([6, 7]).astype(int)
    df["time_bucket"] = df["txn_hour"].apply(_hour_to_bucket)
    return df


def add_amount_features(df: pd.DataFrame) -> pd.DataFrame:
    """Amount band and transaction category features."""
    df = df.copy()
    df["amount_band"] = pd.cut(
        df["Amount"], bins=AMOUNT_BAND_EDGES, labels=AMOUNT_BAND_LABELS, right=False
    ).astype(str)
    # Share of the category's total value represented by this transaction
    category_total = df.groupby("Category")["Amount"].transform("sum")
    df["category_value_share"] = (df["Amount"] / category_total).round(4)
    return df


def add_customer_sequence_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Order each customer's transactions and add backward looking history.

    Features
        customer_txn_seq       1 for the first transaction, 2 for the next ...
        prior_txn_count        transactions before this one
        prior_avg_amount       average amount of earlier transactions
        hours_since_prev_txn   gap from the previous transaction
        prev_location / prev_channel / prev_merchant
    """
    df = df.sort_values(["CustomerID", "txn_datetime", "TransactionID"]).reset_index(drop=True)
    by_customer = df.groupby("CustomerID", sort=False)

    df["customer_txn_seq"] = by_customer.cumcount() + 1
    df["prior_txn_count"] = df["customer_txn_seq"] - 1

    cumulative_spend = by_customer["Amount"].cumsum() - df["Amount"]
    df["prior_avg_amount"] = (cumulative_spend / df["prior_txn_count"].replace(0, np.nan)).round(2)

    previous_time = by_customer["txn_datetime"].shift(1)
    df["hours_since_prev_txn"] = ((df["txn_datetime"] - previous_time).dt.total_seconds() / 3600).round(1)

    df["prev_location"] = by_customer["LocationID"].shift(1)
    df["prev_channel"] = by_customer["Channel"].shift(1)
    df["prev_merchant"] = by_customer["MerchantID"].shift(1)
    return df


def add_merchant_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Merchant frequency features.

        merchant_frequency          transactions at this merchant (all customers)
        merchant_unique_customers   distinct customers of this merchant
        customer_merchant_visit_no  how many times this customer has used it so far
        is_repeat_merchant          1 when the customer used this merchant before
        is_new_category             1 when the customer never used this category before
    """
    df = df.copy()
    df["merchant_frequency"] = df.groupby("MerchantID")["TransactionID"].transform("count")
    df["merchant_unique_customers"] = df.groupby("MerchantID")["CustomerID"].transform("nunique")
    df["customer_merchant_visit_no"] = df.groupby(["CustomerID", "MerchantID"]).cumcount() + 1
    df["is_repeat_merchant"] = (df["customer_merchant_visit_no"] > 1).astype(int)
    df["is_new_category"] = (~df.duplicated(subset=["CustomerID", "Category"], keep="first")).astype(int)
    return df


def add_geo_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Geo features based on location IDs.

        is_home_location           transaction happened at the customer's home location
        location_frequency         transactions seen at this location (all customers)
        customer_location_visit_no how many times this customer has been here so far
        is_new_location            first time this customer transacts at this location
        location_changed           different location from the previous transaction
    """
    df = df.copy()
    df["is_home_location"] = (df["LocationID"] == df["HomeLocationID"]).astype(int)
    df["location_frequency"] = df.groupby("LocationID")["TransactionID"].transform("count")
    df["customer_location_visit_no"] = df.groupby(["CustomerID", "LocationID"]).cumcount() + 1
    df["is_new_location"] = (df["customer_location_visit_no"] == 1).astype(int)
    df["location_changed"] = (df["prev_location"].notna() & (df["LocationID"] != df["prev_location"])).astype(int)
    return df


def add_channel_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Channel features.

        channel_group         Digital or Physical (Branch and ATM)
        is_digital            1 for digital transactions
        is_preferred_channel  channel matches the customer's stated preference
        channel_changed       channel differs from the previous transaction
    """
    df = df.copy()
    df["is_digital"] = df["Channel"].isin(DIGITAL_CHANNELS).astype(int)
    df["channel_group"] = np.where(df["is_digital"] == 1, "Digital", "Physical")
    df["is_preferred_channel"] = (df["Channel"] == df["PreferredChannel"]).astype(int)
    df["channel_changed"] = (df["prev_channel"].notna() & (df["Channel"] != df["prev_channel"])).astype(int)
    return df


def build_transaction_features(merged: pd.DataFrame) -> pd.DataFrame:
    """Run every transaction level feature step in the right order."""
    features = add_merchant_master_features(merged)
    features = add_time_features(features)
    features = add_amount_features(features)
    features = add_customer_sequence_features(features)  # sorts by customer and time
    features = add_merchant_features(features)
    features = add_geo_features(features)
    features = add_channel_features(features)
    logger.info("Transaction features built: %d rows x %d columns", *features.shape)
    return features


# ====================================================================== #
# Customer, merchant and location level features
# ====================================================================== #
def build_customer_features(customers: pd.DataFrame, txn_features: pd.DataFrame) -> pd.DataFrame:
    """
    One row per customer with spend and behaviour profile.

    Customers without transactions are kept with zero spend so that the
    customer dimension stays complete.
    """
    grouped = txn_features.groupby("CustomerID")

    profile = pd.DataFrame(
        {
            "txn_count": grouped["TransactionID"].count(),
            "total_spend": grouped["Amount"].sum().round(2),
            "avg_spend": grouped["Amount"].mean().round(2),
            "median_spend": grouped["Amount"].median().round(2),
            "max_spend": grouped["Amount"].max().round(2),
            "distinct_merchants": grouped["MerchantID"].nunique(),
            "distinct_locations": grouped["LocationID"].nunique(),
            "distinct_categories": grouped["Category"].nunique(),
            "repeat_merchant_txns": grouped["is_repeat_merchant"].sum(),
            "home_location_txns": grouped["is_home_location"].sum(),
            "digital_txns": grouped["is_digital"].sum(),
            "preferred_channel_txns": grouped["is_preferred_channel"].sum(),
            "high_risk_merchant_txns": grouped["is_high_risk_merchant"].sum(),
            "category_mismatch_txns": grouped["is_category_mismatch"].sum(),
            "observed_preferred_channel": grouped["Channel"].agg(mode_with_tiebreak),
            "preferred_location": grouped["LocationID"].agg(mode_with_tiebreak),
            "favourite_category": grouped["Category"].agg(mode_with_tiebreak),
            "first_txn_date": grouped["txn_date"].min().dt.strftime("%Y-%m-%d"),
            "last_txn_date": grouped["txn_date"].max().dt.strftime("%Y-%m-%d"),
        }
    )

    top_location_txns = (
        txn_features.groupby(["CustomerID", "LocationID"]).size().groupby(level=0).max()
    )
    profile["top_location_txns"] = top_location_txns

    profile = profile.reset_index()
    full = customers.merge(profile, on="CustomerID", how="left")

    count_columns = [
        "txn_count", "distinct_merchants", "distinct_locations", "distinct_categories",
        "repeat_merchant_txns", "home_location_txns", "digital_txns",
        "preferred_channel_txns", "top_location_txns", "high_risk_merchant_txns", "category_mismatch_txns",
    ]
    full[count_columns] = full[count_columns].fillna(0).astype(int)
    full[["total_spend"]] = full[["total_spend"]].fillna(0.0)

    active = full["txn_count"] > 0
    full["repeat_merchant_ratio"] = np.where(active, full["repeat_merchant_txns"] / full["txn_count"].clip(lower=1), np.nan).round(4)
    full["geo_consistency_index"] = np.where(active, full["top_location_txns"] / full["txn_count"].clip(lower=1), np.nan).round(4)
    full["home_location_ratio"] = np.where(active, full["home_location_txns"] / full["txn_count"].clip(lower=1), np.nan).round(4)
    full["digital_share"] = np.where(active, full["digital_txns"] / full["txn_count"].clip(lower=1), np.nan).round(4)
    full["channel_loyalty_ratio"] = np.where(active, full["preferred_channel_txns"] / full["txn_count"].clip(lower=1), np.nan).round(4)
    full["is_active"] = active.astype(int)

    logger.info("Customer features built: %d customers (%d active)", len(full), int(active.sum()))
    return full


def build_merchant_dimension(merchants: pd.DataFrame, txn_features: pd.DataFrame) -> pd.DataFrame:
    """
    Merchant dimension: the merchant master plus activity statistics.

    Every merchant in the master is kept, even with no transactions. Merchants
    that appear in transactions but not in the master are added as
    unregistered, so every transaction still has a valid merchant key.
    """
    grouped = txn_features.groupby("MerchantID")
    activity = pd.DataFrame(
        {
            "txn_count": grouped["TransactionID"].count(),
            "unique_customers": grouped["CustomerID"].nunique(),
            "total_value": grouped["Amount"].sum().round(2),
            "avg_value": grouped["Amount"].mean().round(2),
            "primary_txn_category": grouped["Category"].agg(mode_with_tiebreak),
            "category_mismatch_txns": grouped["is_category_mismatch"].sum(),
        }
    )

    master = merchants.rename(
        columns={"MerchantID": "merchant_id", "MerchantName": "merchant_name",
                 "MerchantCategory": "merchant_category", "RiskLevel": "merchant_risk_level"}
    ).assign(is_registered=1)

    unregistered_ids = sorted(set(activity.index) - set(master["merchant_id"]))
    unregistered = pd.DataFrame(
        {
            "merchant_id": unregistered_ids,
            "merchant_name": UNREGISTERED_MERCHANT_LABEL,
            "merchant_category": UNKNOWN_LABEL,
            "merchant_risk_level": UNKNOWN_LABEL,
            "is_registered": 0,
        }
    )

    dim = pd.concat([master, unregistered], ignore_index=True).merge(
        activity, left_on="merchant_id", right_index=True, how="left"
    )
    count_columns = ["txn_count", "unique_customers", "category_mismatch_txns"]
    dim[count_columns] = dim[count_columns].fillna(0).astype(int)
    dim["total_value"] = dim["total_value"].fillna(0.0)
    dim["category_match_ratio"] = np.where(
        dim["txn_count"] > 0, 1 - dim["category_mismatch_txns"] / dim["txn_count"].clip(lower=1), np.nan
    ).round(4)
    return dim.sort_values("merchant_id").reset_index(drop=True)


def build_location_dimension(customers: pd.DataFrame, txn_features: pd.DataFrame) -> pd.DataFrame:
    """
    Location dimension built from the shared location domain.

    It holds every location seen either as a customer home location or as a
    transaction location, with simple activity counts.
    """
    all_locations = sorted(set(customers["HomeLocationID"].astype(str)) | set(txn_features["LocationID"].astype(str)))
    locations = pd.DataFrame({"location_id": all_locations})

    txn_counts = txn_features.groupby("LocationID").agg(
        txn_count=("TransactionID", "count"), total_value=("Amount", "sum")
    )
    home_counts = customers.groupby("HomeLocationID").size().rename("home_customers")

    locations = (
        locations.merge(txn_counts, left_on="location_id", right_index=True, how="left")
        .merge(home_counts, left_on="location_id", right_index=True, how="left")
    )
    locations[["txn_count", "home_customers"]] = locations[["txn_count", "home_customers"]].fillna(0).astype(int)
    locations["total_value"] = locations["total_value"].fillna(0).round(2)
    return locations


def build_all_features(
    merged: pd.DataFrame, customers: pd.DataFrame, merchants: pd.DataFrame
) -> Dict[str, pd.DataFrame]:
    """
    Entry point for the feature stage.

    Returns:
        Dictionary with transaction_features, customer_features,
        merchant_dim and location_dim.
    """
    txn_features = build_transaction_features(merged)
    return {
        "transaction_features": txn_features,
        "customer_features": build_customer_features(customers, txn_features),
        "merchant_dim": build_merchant_dimension(merchants, txn_features),
        "location_dim": build_location_dimension(customers, txn_features),
    }
