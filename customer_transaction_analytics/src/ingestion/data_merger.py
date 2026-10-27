"""
Merge the cleaned source tables into one analytical dataset.

The merge is driven by the relationships found by relationship_detector, so
no join key is hard coded here. The fact table (transactions) is the left
side of every join, which guarantees the row count never changes.
"""

from typing import Dict, List

import pandas as pd

from src.ingestion.relationship_detector import Relationship, find_fact_table
from src.utils.logger import get_logger

logger = get_logger(__name__)


def merge_tables(tables: Dict[str, pd.DataFrame], relationships: List[Relationship]) -> pd.DataFrame:
    """
    Left join every dimension onto the fact table.

    Args:
        tables: Cleaned tables keyed by name.
        relationships: Output of detect_relationships().

    Returns:
        One wide DataFrame with one row per transaction.

    Raises:
        ValueError: if a join would change the number of fact rows.
    """
    fact_table_name = find_fact_table(relationships)
    merged = tables[fact_table_name].copy()
    expected_rows = len(merged)
    logger.info("Fact table identified: '%s' (%d rows)", fact_table_name, expected_rows)

    for relation in relationships:
        if relation.relationship_type != "foreign_key" or relation.child_table != fact_table_name:
            continue

        dimension = tables[relation.parent_table]
        # Avoid name clashes: keep the key and only columns the fact does not have
        new_columns = [c for c in dimension.columns if c not in merged.columns or c == relation.parent_column]
        dimension = dimension[new_columns]

        merged = merged.merge(
            dimension,
            how="left",
            left_on=relation.child_column,
            right_on=relation.parent_column,
            validate="many_to_one",  # fails fast if the dimension key is not unique
        )
        if relation.parent_column != relation.child_column:
            merged = merged.drop(columns=[relation.parent_column])

        logger.info("Joined '%s' on %s", relation.parent_table, relation.child_column)

    if len(merged) != expected_rows:
        raise ValueError(f"Merge changed row count from {expected_rows} to {len(merged)}")

    return merged
