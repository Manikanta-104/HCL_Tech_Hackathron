"""
Automatic relationship discovery between the ingested tables.

Two kinds of links are detected from the data itself:

1. Foreign keys
   Column B.x references A.y when A.y is unique (a candidate key) and almost
   every value of B.x exists in A.y (value containment).

2. Shared domains (conformed dimensions)
   Two ID columns in different tables that carry the same kind of ID (same
   prefix, for example L for location) but where no table owns the key.
   HomeLocationID in customers and LocationID in transactions are an example.
   These become a derived dimension table (dim_location) in the database.
"""

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Share of child values that must exist in the parent key to call it a foreign key
FK_CONTAINMENT_THRESHOLD = 0.90
# Share of values that must carry the same alphabetic prefix to share a domain
DOMAIN_PREFIX_THRESHOLD = 0.95
# Raw data can hold a few nulls or duplicate keys (cleaning fixes those later),
# so a column counts as a candidate key when it is almost complete and unique
KEY_COMPLETENESS_THRESHOLD = 0.95
KEY_UNIQUENESS_THRESHOLD = 0.95


@dataclass(frozen=True)
class Relationship:
    """A detected link between two tables."""

    relationship_type: str  # "foreign_key" or "shared_domain"
    parent_table: str
    parent_column: str
    child_table: str
    child_column: str
    match_ratio: float

    def describe(self) -> str:
        """One line human readable description."""
        arrow = "->" if self.relationship_type == "foreign_key" else "<->"
        return (
            f"{self.child_table}.{self.child_column} {arrow} {self.parent_table}.{self.parent_column} "
            f"[{self.relationship_type}, match={self.match_ratio:.0%}]"
        )


def _id_prefix(series: pd.Series) -> str:
    """Return the dominant alphabetic prefix of an ID column, or empty string."""
    prefixes = series.dropna().astype(str).str.extract(r"^([A-Za-z]+)")[0].dropna()
    if prefixes.empty:
        return ""
    top = prefixes.value_counts(normalize=True)
    return top.index[0] if top.iloc[0] >= DOMAIN_PREFIX_THRESHOLD else ""


def _candidate_keys(tables: Dict[str, pd.DataFrame]) -> List[tuple]:
    """
    Columns that are (almost) unique and populated, so they can act as a key.

    Thresholds are slightly below 100% because this runs on raw data, before
    duplicates and null IDs have been quarantined.
    """
    keys = []
    for table_name, frame in tables.items():
        for column in frame.columns:
            if not column.lower().endswith("id") or frame.empty:
                continue
            values = frame[column]
            non_null = values.dropna()
            completeness = len(non_null) / len(values)
            uniqueness = non_null.nunique() / max(len(non_null), 1)
            if completeness >= KEY_COMPLETENESS_THRESHOLD and uniqueness >= KEY_UNIQUENESS_THRESHOLD:
                keys.append((table_name, column))
    return keys


def detect_relationships(tables: Dict[str, pd.DataFrame]) -> List[Relationship]:
    """
    Detect foreign keys and shared domains between all table pairs.

    Args:
        tables: Mapping of table name to DataFrame.

    Returns:
        List of Relationship objects, foreign keys first.
    """
    relationships: List[Relationship] = []
    candidate_keys = _candidate_keys(tables)
    linked_columns = set()

    # --- Foreign keys: value containment against candidate keys -------------
    for parent_table, parent_column in candidate_keys:
        parent_values = set(tables[parent_table][parent_column].dropna().astype(str))
        for child_table, child_frame in tables.items():
            if child_table == parent_table:
                continue
            for child_column in child_frame.columns:
                if not child_column.lower().endswith("id"):
                    continue
                child_values = child_frame[child_column].dropna().astype(str)
                if child_values.empty:
                    continue
                containment = child_values.isin(parent_values).mean()
                if containment >= FK_CONTAINMENT_THRESHOLD:
                    relationships.append(
                        Relationship("foreign_key", parent_table, parent_column,
                                     child_table, child_column, round(float(containment), 4))
                    )
                    linked_columns.add((child_table, child_column))

    # --- Shared domains: same ID prefix, no owning key table ----------------
    id_columns = []
    for table_name, frame in tables.items():
        for column in frame.columns:
            if column.lower().endswith("id") and (table_name, column) not in linked_columns:
                prefix = _id_prefix(frame[column])
                if prefix:
                    id_columns.append((table_name, column, prefix))

    key_set = set(candidate_keys)
    for i, (table_a, column_a, prefix_a) in enumerate(id_columns):
        for table_b, column_b, prefix_b in id_columns[i + 1:]:
            if table_a == table_b or prefix_a != prefix_b:
                continue
            # Skip pairs where one side is a primary key, those are FK candidates
            if (table_a, column_a) in key_set or (table_b, column_b) in key_set:
                continue
            values_a = set(tables[table_a][column_a].dropna().astype(str))
            values_b = set(tables[table_b][column_b].dropna().astype(str))
            overlap = len(values_a & values_b) / max(len(values_a | values_b), 1)
            relationships.append(
                Relationship("shared_domain", table_a, column_a, table_b, column_b, round(overlap, 4))
            )

    for relation in relationships:
        logger.info("Detected relationship: %s", relation.describe())
    return relationships


def find_fact_table(relationships: List[Relationship]) -> str:
    """The fact table is the one that references the most other tables."""
    fk_counts: Dict[str, int] = {}
    for relation in relationships:
        if relation.relationship_type == "foreign_key":
            fk_counts[relation.child_table] = fk_counts.get(relation.child_table, 0) + 1
    if not fk_counts:
        raise ValueError("No foreign key relationships detected, cannot identify the fact table")
    return max(fk_counts, key=fk_counts.get)
