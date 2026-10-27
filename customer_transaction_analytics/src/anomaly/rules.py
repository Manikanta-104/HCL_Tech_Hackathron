"""
Rule based anomaly detection: rule catalogue.

Each rule is a plain function that receives the transaction feature table
and the threshold config, and returns two aligned Series:
    flagged : boolean, True where the rule fires
    details : text explaining why, shown to analysts in the dashboard

No machine learning is used. Every alert can be explained in one sentence,
which is what fraud and compliance teams expect from a first line control.
"""

from dataclasses import dataclass
from typing import Callable, List, Tuple

import numpy as np
import pandas as pd

RuleOutput = Tuple[pd.Series, pd.Series]


@dataclass(frozen=True)
class AnomalyRule:
    """Metadata plus the evaluation function of one business rule."""

    code: str
    name: str
    description: str
    severity: str  # Low, Medium or High
    evaluate: Callable[[pd.DataFrame, dict], RuleOutput]


def _empty_details(df: pd.DataFrame) -> pd.Series:
    return pd.Series("", index=df.index, dtype=object)


# ---------------------------------------------------------------------- #
# Rule functions
# ---------------------------------------------------------------------- #
def rule_high_value(df: pd.DataFrame, cfg: dict) -> RuleOutput:
    """Transaction value in the top percentile of all transactions."""
    threshold = float(df["Amount"].quantile(cfg["high_value_percentile"]))
    flagged = df["Amount"] >= threshold
    details = _empty_details(df)
    details[flagged] = df.loc[flagged, "Amount"].map(
        lambda amount: f"Amount {amount:,.2f} is at or above the P{int(cfg['high_value_percentile'] * 100)} "
                       f"threshold of {threshold:,.2f}"
    )
    return flagged, details


def rule_odd_hour(df: pd.DataFrame, cfg: dict) -> RuleOutput:
    """Transaction made in the late night window."""
    start, end = cfg["odd_hour_start"], cfg["odd_hour_end"]
    flagged = df["txn_hour"].between(start, end)
    details = _empty_details(df)
    details[flagged] = df.loc[flagged, "txn_hour"].map(
        lambda hour: f"Transaction at {hour:02d}:00, inside the unusual window {start:02d}:00 to {end:02d}:59"
    )
    return flagged, details


def rule_sudden_location_change(df: pd.DataFrame, cfg: dict) -> RuleOutput:
    """New location, away from home, shortly after a transaction elsewhere."""
    window = cfg["location_change_window_hours"]
    flagged = (
        (df["location_changed"] == 1)
        & (df["is_home_location"] == 0)
        & (df["hours_since_prev_txn"] <= window)
    ).fillna(False)
    details = _empty_details(df)
    details[flagged] = df.loc[flagged].apply(
        lambda r: f"Moved from {r['prev_location']} to {r['LocationID']} within "
                  f"{r['hours_since_prev_txn']:.0f} h (home is {r['HomeLocationID']})",
        axis=1,
    )
    return flagged.astype(bool), details


def rule_merchant_change(df: pd.DataFrame, cfg: dict) -> RuleOutput:
    """Established customer suddenly uses a new merchant in a new category."""
    flagged = (
        (df["prior_txn_count"] >= cfg["min_history_for_behaviour"])
        & (df["is_repeat_merchant"] == 0)
        & (df["is_new_category"] == 1)
    )
    details = _empty_details(df)
    details[flagged] = df.loc[flagged].apply(
        lambda r: f"First ever {r['Category']} spend, at new merchant {r['MerchantID']}, "
                  f"after {int(r['prior_txn_count'])} earlier transactions",
        axis=1,
    )
    return flagged, details


def rule_behaviour_change(df: pd.DataFrame, cfg: dict) -> RuleOutput:
    """Spend far above or far below the customer's own running average."""
    has_history = df["prior_txn_count"] >= cfg["min_history_for_behaviour"]
    ratio = df["Amount"] / df["prior_avg_amount"].replace(0, np.nan)
    spike = ratio >= cfg["behaviour_spike_multiplier"]
    drop = ratio <= cfg["behaviour_drop_multiplier"]
    flagged = (has_history & (spike | drop)).fillna(False).astype(bool)
    details = _empty_details(df)
    details[flagged] = df.loc[flagged].apply(
        lambda r: f"Spent {r['Amount']:,.2f}, which is {r['Amount'] / r['prior_avg_amount']:.1f}x the "
                  f"customer's average of {r['prior_avg_amount']:,.2f}",
        axis=1,
    )
    return flagged, details


def rule_digital_to_branch(df: pd.DataFrame, cfg: dict) -> RuleOutput:
    """A digital first customer turns up at a branch."""
    flagged = (df["PreferredChannel"] == "Digital") & (df["Channel"] == "Branch")
    details = _empty_details(df)
    details[flagged] = "Customer prefers Digital but transacted at a Branch"
    return flagged, details


def rule_channel_change(df: pd.DataFrame, cfg: dict) -> RuleOutput:
    """Channel switched from the previous transaction to a non preferred channel."""
    digital_to_branch = (df["PreferredChannel"] == "Digital") & (df["Channel"] == "Branch")
    flagged = (
        (df["channel_changed"] == 1)
        & (df["is_preferred_channel"] == 0)
        & ~digital_to_branch  # already covered by its own rule
    )
    details = _empty_details(df)
    details[flagged] = df.loc[flagged].apply(
        lambda r: f"Switched from {r['prev_channel']} to {r['Channel']} (preferred: {r['PreferredChannel']})",
        axis=1,
    )
    return flagged, details


def rule_high_risk_merchant(df: pd.DataFrame, cfg: dict) -> RuleOutput:
    """Payment to a merchant rated High risk, or to one missing from the merchant master."""
    flagged = df["MerchantRiskLevel"].isin(cfg["high_risk_merchant_levels"])
    details = _empty_details(df)
    details[flagged] = df.loc[flagged].apply(
        lambda r: f"Paid {r['Amount']:,.2f} to {r['MerchantName']} ({r['MerchantID']}), "
                  + ("not in the merchant master" if r["MerchantRiskLevel"] == "Unknown"
                     else f"rated {r['MerchantRiskLevel']} risk"),
        axis=1,
    )
    return flagged, details


def rule_category_mismatch_at_risky_merchant(df: pd.DataFrame, cfg: dict) -> RuleOutput:
    """
    Transaction category does not match the merchant's registered category,
    at a merchant rated Medium or High risk. Mismatches at low risk merchants
    are common and only tracked as a KPI, so they do not flood the queue.
    """
    flagged = (df["is_category_mismatch"] == 1) & df["MerchantRiskLevel"].isin(cfg["mismatch_watch_risk_levels"])
    details = _empty_details(df)
    details[flagged] = df.loc[flagged].apply(
        lambda r: f"Booked as {r['Category']} at {r['MerchantName']}, which is registered as "
                  f"{r['MerchantCategory']} ({r['MerchantRiskLevel']} risk merchant)",
        axis=1,
    )
    return flagged, details


# ---------------------------------------------------------------------- #
# Catalogue
# ---------------------------------------------------------------------- #
RULE_CATALOGUE: List[AnomalyRule] = [
    AnomalyRule("R01_HIGH_VALUE", "High value transaction",
                "Amount at or above the configured percentile of all transactions", "High", rule_high_value),
    AnomalyRule("R02_ODD_HOUR", "Unusual transaction time",
                "Transaction during the late night window", "Medium", rule_odd_hour),
    AnomalyRule("R03_LOCATION_JUMP", "Sudden location change",
                "New non home location shortly after a transaction somewhere else", "High",
                rule_sudden_location_change),
    AnomalyRule("R04_MERCHANT_CHANGE", "Sudden merchant change",
                "Established customer uses a new merchant in a category never used before", "Medium",
                rule_merchant_change),
    AnomalyRule("R05_BEHAVIOUR_CHANGE", "Spending behaviour change",
                "Amount far above or below the customer's own running average", "Medium",
                rule_behaviour_change),
    AnomalyRule("R06_DIGITAL_TO_BRANCH", "Digital to branch shift",
                "Digital first customer transacts at a branch", "Medium", rule_digital_to_branch),
    AnomalyRule("R07_CHANNEL_CHANGE", "Channel change",
                "Channel switched to one the customer does not normally use", "Low", rule_channel_change),
    AnomalyRule("R08_HIGH_RISK_MERCHANT", "High risk merchant",
                "Payment to a merchant rated High risk or missing from the merchant master", "High",
                rule_high_risk_merchant),
    AnomalyRule("R09_CATEGORY_MISMATCH", "Category mismatch at risky merchant",
                "Transaction category differs from the registered category of a Medium or High risk merchant",
                "Medium", rule_category_mismatch_at_risky_merchant),
]
