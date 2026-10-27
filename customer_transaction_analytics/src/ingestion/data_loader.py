"""
Data ingestion module.

Responsibilities
1. Discover every CSV file in the landing zone (data/raw).
2. Read each file with Pandas as text, so nothing is silently converted.
3. Work out which logical table each file holds by comparing its columns
   with the schema registry (file names are not trusted).
4. Validate the schema: missing columns, unexpected columns and whether the
   values can be converted to the expected data types.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from src.ingestion.schema_registry import MIN_SCHEMA_MATCH_SCORE, SCHEMA_REGISTRY, TableSchema
from src.utils.config import NULL_TOKENS, RAW_DATA_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SchemaValidationResult:
    """Outcome of validating one file against its schema."""

    table_name: str
    file_name: str
    row_count: int
    column_count: int
    missing_columns: List[str] = field(default_factory=list)
    extra_columns: List[str] = field(default_factory=list)
    type_issues: Dict[str, int] = field(default_factory=dict)  # column -> bad value count
    pattern_issues: Dict[str, int] = field(default_factory=dict)  # column -> bad id count

    @property
    def is_valid(self) -> bool:
        """A file is usable when no required column is missing."""
        schema = SCHEMA_REGISTRY[self.table_name]
        return not any(col in schema.required_columns for col in self.missing_columns)

    def to_dict(self) -> dict:
        """Serialisable view used in reports."""
        return {
            "table": self.table_name,
            "file": self.file_name,
            "rows": self.row_count,
            "columns": self.column_count,
            "missing_columns": self.missing_columns,
            "extra_columns": self.extra_columns,
            "type_issues": self.type_issues,
            "pattern_issues": self.pattern_issues,
            "is_valid": self.is_valid,
        }


@dataclass
class IngestionResult:
    """Everything produced by the ingestion stage."""

    tables: Dict[str, pd.DataFrame]
    validations: Dict[str, SchemaValidationResult]
    unmatched_files: List[str]

    @property
    def total_raw_rows(self) -> int:
        """Row count across all ingested tables."""
        return int(sum(len(df) for df in self.tables.values()))


def discover_csv_files(source_dir: Path = RAW_DATA_DIR) -> List[Path]:
    """Return all CSV files in the landing zone, sorted by name."""
    files = sorted(source_dir.glob("*.csv"))
    logger.info("Found %d CSV file(s) in %s", len(files), source_dir)
    return files


def read_csv_as_text(file_path: Path) -> pd.DataFrame:
    """
    Read a CSV keeping every value as text.

    Reading as text means the cleaning stage, not Pandas, decides how to deal
    with values such as "1,200" or "abc" in a numeric column.
    """
    frame = pd.read_csv(
        file_path,
        dtype=str,
        keep_default_na=True,
        na_values=NULL_TOKENS,
        skipinitialspace=True,
        encoding="utf-8-sig",  # tolerates the BOM Excel adds to CSV exports
    )
    frame.columns = [str(col).strip() for col in frame.columns]
    return frame


def identify_table(frame: pd.DataFrame) -> Optional[TableSchema]:
    """
    Match a DataFrame to the schema whose columns it covers best.

    Returns:
        The matching TableSchema, or None when no schema reaches the minimum
        column match score.
    """
    file_columns = set(frame.columns)
    best_schema, best_score = None, 0.0

    for schema in SCHEMA_REGISTRY.values():
        expected = set(schema.column_names)
        score = len(expected & file_columns) / len(expected)
        if score > best_score:
            best_schema, best_score = schema, score

    if best_score >= MIN_SCHEMA_MATCH_SCORE:
        return best_schema
    return None


def _count_type_issues(series: pd.Series, logical_type: str) -> int:
    """Count non null values that cannot be converted to the logical type."""
    values = series.dropna()
    if values.empty:
        return 0
    if logical_type == "float":
        converted = pd.to_numeric(values.str.replace(",", "", regex=False), errors="coerce")
        return int(converted.isna().sum())
    if logical_type == "int":
        converted = pd.to_numeric(values, errors="coerce")
        bad_numbers = converted.isna()
        not_whole = converted.notna() & (converted % 1 != 0)
        return int((bad_numbers | not_whole).sum())
    if logical_type == "date":
        converted = pd.to_datetime(values, errors="coerce")
        return int(converted.isna().sum())
    return 0


def validate_schema(frame: pd.DataFrame, schema: TableSchema, file_name: str) -> SchemaValidationResult:
    """
    Validate a DataFrame against its schema.

    Checks performed
        - required and optional columns are present
        - columns that are not part of the schema
        - values that cannot be converted to the expected type
        - IDs that do not follow the expected pattern (for example C001)
    """
    result = SchemaValidationResult(
        table_name=schema.name,
        file_name=file_name,
        row_count=len(frame),
        column_count=frame.shape[1],
        missing_columns=[col for col in schema.column_names if col not in frame.columns],
        extra_columns=[col for col in frame.columns if col not in schema.columns],
    )

    for column, logical_type in schema.columns.items():
        if column not in frame.columns:
            continue
        bad_count = _count_type_issues(frame[column], logical_type)
        if bad_count:
            result.type_issues[column] = bad_count

    for column, pattern in schema.id_patterns.items():
        if column not in frame.columns:
            continue
        values = frame[column].dropna().str.strip()
        bad_count = int((~values.str.match(pattern)).sum())
        if bad_count:
            result.pattern_issues[column] = bad_count

    return result


def ingest_raw_data(source_dir: Path = RAW_DATA_DIR) -> IngestionResult:
    """
    Run the full ingestion stage.

    Returns:
        IngestionResult with one DataFrame per logical table.

    Raises:
        FileNotFoundError: if the landing zone has no CSV files.
        ValueError: if a mandatory table is missing or fails validation.
    """
    csv_files = discover_csv_files(source_dir)
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {source_dir}")

    tables: Dict[str, pd.DataFrame] = {}
    validations: Dict[str, SchemaValidationResult] = {}
    unmatched: List[str] = []

    for file_path in csv_files:
        frame = read_csv_as_text(file_path)
        schema = identify_table(frame)

        if schema is None:
            logger.warning("File %s does not match any known schema and is skipped", file_path.name)
            unmatched.append(file_path.name)
            continue

        validation = validate_schema(frame, schema, file_path.name)
        logger.info(
            "File %-20s -> table '%s' (%d rows, %d cols, valid=%s)",
            file_path.name, schema.name, validation.row_count, validation.column_count, validation.is_valid,
        )
        if validation.type_issues:
            logger.warning("  Type issues in %s: %s", schema.name, validation.type_issues)
        if validation.pattern_issues:
            logger.warning("  ID pattern issues in %s: %s", schema.name, validation.pattern_issues)

        if schema.name in tables:
            # Several files for the same table (for example monthly drops) are stacked
            logger.info("  Appending %s to existing '%s' table", file_path.name, schema.name)
            tables[schema.name] = pd.concat([tables[schema.name], frame], ignore_index=True)
        else:
            tables[schema.name] = frame
        validations[schema.name] = validation

    missing_tables = [name for name in SCHEMA_REGISTRY if name not in tables]
    if missing_tables:
        raise ValueError(f"Mandatory source table(s) missing from landing zone: {missing_tables}")

    invalid = [name for name, check in validations.items() if not check.is_valid]
    if invalid:
        raise ValueError(f"Schema validation failed for: {invalid}")

    return IngestionResult(tables=tables, validations=validations, unmatched_files=unmatched)
