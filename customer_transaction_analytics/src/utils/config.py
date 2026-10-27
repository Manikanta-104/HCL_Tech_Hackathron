"""
Central configuration for the Customer Transaction Analytics Platform.

Every path, business constant and anomaly threshold lives here so that the
rest of the code base never hard codes a value. Changing a rule threshold or
a folder location is a one line change in this file.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Project paths
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"              # Landing zone: CSV files as received
PROCESSED_DATA_DIR = DATA_DIR / "processed"  # Cleaned and feature engineered data
OUTPUT_DATA_DIR = DATA_DIR / "output"        # SQLite database and KPI extracts
REPORTS_DIR = PROJECT_ROOT / "reports"       # Human readable run reports

SQL_DIR = PROJECT_ROOT / "src" / "database" / "sql"
SCHEMA_SQL_PATH = SQL_DIR / "schema.sql"
VIEWS_SQL_PATH = SQL_DIR / "views.sql"
KPI_SQL_PATH = SQL_DIR / "kpi_queries.sql"

DATABASE_PATH = OUTPUT_DATA_DIR / "customer_analytics.db"
LOG_FILE_PATH = REPORTS_DIR / "pipeline_run.log"

# --------------------------------------------------------------------------
# Business reference values used during cleaning
# --------------------------------------------------------------------------
VALID_CHANNELS = ["Digital", "Branch", "ATM"]
VALID_SEGMENTS = ["Student", "Standard", "Premium"]
VALID_MERCHANT_RISK_LEVELS = ["Low", "Medium", "High"]

# Free text variants seen in real bank feeds, mapped to the canonical value
CHANNEL_SYNONYMS = {
    "online": "Digital",
    "internet": "Digital",
    "mobile": "Digital",
    "app": "Digital",
    "upi": "Digital",
    "netbanking": "Digital",
    "digital": "Digital",
    "branch": "Branch",
    "counter": "Branch",
    "atm": "ATM",
}

# Channel grouping used for the Digital vs Physical mix KPI
DIGITAL_CHANNELS = ["Digital"]
PHYSICAL_CHANNELS = ["Branch", "ATM"]

UNKNOWN_LABEL = "Unknown"
UNCATEGORIZED_LABEL = "Uncategorized"
# Transactions whose MerchantID is missing from the merchant master are kept
# (the payment really happened) but the merchant is marked as unregistered
UNREGISTERED_MERCHANT_LABEL = "Unregistered merchant"

# A single transaction above this value is treated as a data entry error
MAX_VALID_TRANSACTION_AMOUNT = 10_000_000

# Strings that should be read as missing values
NULL_TOKENS = ["", " ", "na", "n/a", "nan", "null", "none", "-", "?"]

# --------------------------------------------------------------------------
# Feature engineering settings
# --------------------------------------------------------------------------
# Hour ranges (inclusive) for each part of the day
TIME_BUCKETS = {
    "Night (00-05)": (0, 5),
    "Morning (06-11)": (6, 11),
    "Afternoon (12-17)": (12, 17),
    "Evening (18-23)": (18, 23),
}

# Amount bands: upper edges of each band, the last band is open ended
AMOUNT_BAND_EDGES = [0, 500, 1500, 3000, float("inf")]
AMOUNT_BAND_LABELS = ["Low (<500)", "Medium (500-1.5K)", "High (1.5K-3K)", "Very High (3K+)"]

# --------------------------------------------------------------------------
# Rule based anomaly detection thresholds
# --------------------------------------------------------------------------
ANOMALY_RULES_CONFIG = {
    # R1: transaction value at or above this percentile of all transactions
    "high_value_percentile": 0.95,
    # R2: hours treated as unusual for retail banking activity (inclusive)
    "odd_hour_start": 0,
    "odd_hour_end": 4,
    # R3: a location jump within this many hours of the previous transaction
    "location_change_window_hours": 168,
    # R4 and R5 need some history before a "change" can be judged
    "min_history_for_behaviour": 2,
    # R5: spend spike or drop versus the customer's own running average
    "behaviour_spike_multiplier": 2.0,
    "behaviour_drop_multiplier": 0.25,
    # R08: merchant risk levels that always raise an alert ("Unknown" covers
    # merchants that are not in the merchant master)
    "high_risk_merchant_levels": ["High", "Unknown"],
    # R09: merchant risk levels where a category mismatch is worth an alert
    "mismatch_watch_risk_levels": ["Medium", "High"],
}

# Points added to the risk score for each severity level
SEVERITY_WEIGHTS = {"Low": 1, "Medium": 2, "High": 3}

# Risk score bands: (lower bound inclusive, label). Checked from top to bottom.
RISK_LEVEL_BANDS = [(5, "High"), (3, "Medium"), (1, "Low"), (0, "None")]
