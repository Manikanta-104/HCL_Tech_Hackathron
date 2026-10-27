"""
Rule based anomaly detector.

Runs every rule in the catalogue, then
    1. creates one alert row per (transaction, rule) hit
    2. adds up severity weights into a transaction risk score
    3. maps the score to a risk level (None, Low, Medium, High)

The output feeds two SQLite tables: anomaly_alerts and transaction_risk.
"""

from typing import Dict, List

import pandas as pd

from src.anomaly.rules import RULE_CATALOGUE, AnomalyRule
from src.utils.config import ANOMALY_RULES_CONFIG, RISK_LEVEL_BANDS, SEVERITY_WEIGHTS
from src.utils.logger import get_logger

logger = get_logger(__name__)


def score_to_risk_level(score: int) -> str:
    """Translate a numeric risk score into a label using RISK_LEVEL_BANDS."""
    for lower_bound, label in RISK_LEVEL_BANDS:
        if score >= lower_bound:
            return label
    return "None"


def rule_catalogue_frame(rules: List[AnomalyRule] = RULE_CATALOGUE) -> pd.DataFrame:
    """Rule metadata as a DataFrame, stored in the database for transparency."""
    return pd.DataFrame(
        [
            {
                "rule_code": rule.code,
                "rule_name": rule.name,
                "description": rule.description,
                "severity": rule.severity,
                "severity_weight": SEVERITY_WEIGHTS[rule.severity],
            }
            for rule in rules
        ]
    )


def detect_anomalies(
    txn_features: pd.DataFrame,
    rules: List[AnomalyRule] = RULE_CATALOGUE,
    config: Dict = ANOMALY_RULES_CONFIG,
) -> Dict[str, pd.DataFrame]:
    """
    Apply all rules to the transaction features.

    Args:
        txn_features: Output of feature engineering.
        rules: Rules to evaluate, the full catalogue by default.
        config: Threshold values.

    Returns:
        Dictionary with 'alerts', 'transaction_risk' and 'rules' DataFrames.
    """
    alert_frames = []
    base_columns = ["TransactionID", "CustomerID", "txn_datetime", "Amount", "Channel", "LocationID", "MerchantID"]

    for rule in rules:
        flagged, details = rule.evaluate(txn_features, config)
        hits = txn_features.loc[flagged, base_columns].copy()
        hits["rule_code"] = rule.code
        hits["rule_name"] = rule.name
        hits["severity"] = rule.severity
        hits["severity_weight"] = SEVERITY_WEIGHTS[rule.severity]
        hits["details"] = details[flagged].values
        alert_frames.append(hits)
        logger.info("Rule %-22s fired on %3d transaction(s)", rule.code, len(hits))

    alerts = pd.concat(alert_frames, ignore_index=True) if alert_frames else pd.DataFrame(columns=base_columns)
    alerts = alerts.sort_values(["txn_datetime", "TransactionID", "severity_weight"], ascending=[True, True, False])
    alerts = alerts.reset_index(drop=True)
    alerts.insert(0, "alert_id", [f"A{i:05d}" for i in range(1, len(alerts) + 1)])

    # Risk score per transaction (transactions without hits get zero)
    per_txn = alerts.groupby("TransactionID").agg(
        rules_triggered=("rule_code", "count"),
        risk_score=("severity_weight", "sum"),
        rule_codes=("rule_code", lambda codes: ", ".join(sorted(codes))),
    )
    risk = txn_features[["TransactionID", "CustomerID"]].merge(
        per_txn, left_on="TransactionID", right_index=True, how="left"
    )
    risk["rules_triggered"] = risk["rules_triggered"].fillna(0).astype(int)
    risk["risk_score"] = risk["risk_score"].fillna(0).astype(int)
    risk["rule_codes"] = risk["rule_codes"].fillna("")
    risk["risk_level"] = risk["risk_score"].apply(score_to_risk_level)

    flagged_txns = int((risk["rules_triggered"] > 0).sum())
    logger.info(
        "Anomaly detection complete: %d alerts on %d of %d transactions (High risk: %d)",
        len(alerts), flagged_txns, len(risk), int((risk["risk_level"] == "High").sum()),
    )
    return {"alerts": alerts, "transaction_risk": risk, "rules": rule_catalogue_frame(rules)}
