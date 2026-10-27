"""
KPI query library.

Reads the named queries in kpi_queries.sql and turns user filters into a
parameterised "ft" CTE. Values are always passed as SQL parameters, never
pasted into the SQL text, so the dashboard is safe from SQL injection.
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.utils.config import KPI_SQL_PATH

_NAME_PATTERN = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.MULTILINE)


@dataclass
class TransactionFilters:
    """Filters the dashboard (or any caller) can apply to the KPI queries."""

    start_date: Optional[str] = None          # ISO date, inclusive
    end_date: Optional[str] = None            # ISO date, inclusive
    segments: List[str] = field(default_factory=list)
    channels: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    risk_levels: List[str] = field(default_factory=list)
    merchant_risk_levels: List[str] = field(default_factory=list)
    customer_id: Optional[str] = None

    def is_empty(self) -> bool:
        """True when no filter is set."""
        return not any(
            [self.start_date, self.end_date, self.segments, self.channels,
             self.categories, self.risk_levels, self.merchant_risk_levels, self.customer_id]
        )


@lru_cache(maxsize=4)
def load_query_library(sql_path: Path = KPI_SQL_PATH) -> Dict[str, str]:
    """
    Parse kpi_queries.sql into {query_name: sql_text}.

    Each query begins with a line "-- name: <query_name>" and runs until the
    next such line.
    """
    text = Path(sql_path).read_text(encoding="utf-8")
    matches = list(_NAME_PATTERN.finditer(text))
    library = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        # Drop trailing section banners that belong to the next query
        body = re.sub(r"(\n--[^\n]*)+\s*$", "", body).strip()
        library[match.group(1)] = body.rstrip(";").strip()
    return library


def _in_clause(column: str, values: List[str], prefix: str, params: dict) -> str:
    """Build 'column IN (:p0, :p1)' and add the values to params."""
    placeholders = []
    for index, value in enumerate(values):
        key = f"{prefix}_{index}"
        params[key] = value
        placeholders.append(f":{key}")
    return f"{column} IN ({', '.join(placeholders)})"


def build_filter_cte(filters: Optional[TransactionFilters] = None) -> Tuple[str, dict]:
    """
    Build the 'ft' CTE body and its parameters.

    Returns:
        (sql for the CTE body, parameter dictionary)
    """
    filters = filters or TransactionFilters()
    conditions, params = ["1 = 1"], {}

    if filters.start_date:
        conditions.append("txn_date >= :start_date")
        params["start_date"] = filters.start_date
    if filters.end_date:
        conditions.append("txn_date <= :end_date")
        params["end_date"] = filters.end_date
    if filters.segments:
        conditions.append(_in_clause("segment", filters.segments, "seg", params))
    if filters.channels:
        conditions.append(_in_clause("channel", filters.channels, "chn", params))
    if filters.categories:
        conditions.append(_in_clause("category", filters.categories, "cat", params))
    if filters.risk_levels:
        conditions.append(_in_clause("risk_level", filters.risk_levels, "risk", params))
    if filters.merchant_risk_levels:
        conditions.append(_in_clause("merchant_risk_level", filters.merchant_risk_levels, "mrisk", params))
    if filters.customer_id:
        conditions.append("customer_id = :customer_id")
        params["customer_id"] = filters.customer_id

    cte_body = "SELECT * FROM vw_transaction_details WHERE " + " AND ".join(conditions)
    return cte_body, params


def compose_query(query_sql: str, filters: Optional[TransactionFilters] = None) -> Tuple[str, dict]:
    """
    Put the 'ft' CTE in front of a library query.

    If the query already starts with WITH, the ft CTE is added as the first
    entry of that WITH list. Otherwise a new WITH clause is created.
    """
    cte_body, params = build_filter_cte(filters)
    stripped = re.sub(r"^(\s*--[^\n]*\n)*", "", query_sql).lstrip()  # skip leading comments
    if re.match(r"(?i)^with\s", stripped):
        sql = re.sub(r"(?i)^with\s", f"WITH ft AS ({cte_body}),\n", stripped, count=1)
    else:
        sql = f"WITH ft AS ({cte_body})\n{stripped}"
    return sql, params
