"""
Schema registry for the landing zone.

Each entry describes one logical source table: its columns, the expected
data type of every column, the primary key, mandatory columns and the
pattern every ID must follow. Files are matched to these schemas by their
columns, not by their file names, so a renamed file is still recognised.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class TableSchema:
    """Expected structure of one source table."""

    name: str
    description: str
    columns: Dict[str, str]                # column name -> logical type
    primary_key: str
    required_columns: List[str]
    id_patterns: Dict[str, str] = field(default_factory=dict)  # column -> regex

    @property
    def column_names(self) -> List[str]:
        """List of expected column names in order."""
        return list(self.columns.keys())


# Logical types understood by the validator: id, string, category, float, int, date
CUSTOMERS_SCHEMA = TableSchema(
    name="customers",
    description="Customer master data (one row per customer)",
    columns={
        "CustomerID": "id",
        "CustomerName": "string",
        "Segment": "category",
        "HomeLocationID": "id",
        "PreferredChannel": "category",
    },
    primary_key="CustomerID",
    required_columns=["CustomerID"],
    id_patterns={"CustomerID": r"^C\d+$", "HomeLocationID": r"^L\d+$"},
)

MERCHANTS_SCHEMA = TableSchema(
    name="merchants",
    description="Merchant master data (one row per merchant)",
    columns={
        "MerchantID": "id",
        "MerchantName": "string",
        "MerchantCategory": "category",
        "RiskLevel": "category",
    },
    primary_key="MerchantID",
    required_columns=["MerchantID"],
    id_patterns={"MerchantID": r"^M\d+$"},
)

TIME_SCHEMA = TableSchema(
    name="time",
    description="Time dimension (one row per time slot)",
    columns={
        "TimeID": "id",
        "Date": "date",
        "DayOfWeek": "category",
        "Month": "category",
        "Year": "int",
        "HourOfDay": "int",
    },
    primary_key="TimeID",
    required_columns=["TimeID", "Date", "HourOfDay"],
    id_patterns={"TimeID": r"^T\d+$"},
)

TRANSACTIONS_SCHEMA = TableSchema(
    name="transactions",
    description="Transaction fact data (one row per transaction)",
    columns={
        "TransactionID": "id",
        "CustomerID": "id",
        "MerchantID": "id",
        "TimeID": "id",
        "LocationID": "id",
        "Amount": "float",
        "Category": "category",
        "Channel": "category",
    },
    primary_key="TransactionID",
    required_columns=["TransactionID", "CustomerID", "TimeID", "Amount"],
    id_patterns={
        "TransactionID": r"^T\d+$",
        "CustomerID": r"^C\d+$",
        "MerchantID": r"^M\d+$",
        "TimeID": r"^T\d+$",
        "LocationID": r"^L\d+$",
    },
)

SCHEMA_REGISTRY: Dict[str, TableSchema] = {
    schema.name: schema
    for schema in (CUSTOMERS_SCHEMA, MERCHANTS_SCHEMA, TIME_SCHEMA, TRANSACTIONS_SCHEMA)
}

# Share of a schema's columns a file must contain to be matched to it
MIN_SCHEMA_MATCH_SCORE = 0.8
