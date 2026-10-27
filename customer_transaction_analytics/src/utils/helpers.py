"""
Small, reusable helper functions shared across modules.
"""

import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

from src.utils.config import DATA_DIR, OUTPUT_DATA_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, REPORTS_DIR


def ensure_project_directories() -> None:
    """Create every data and report folder if it does not exist yet."""
    for folder in (DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, OUTPUT_DATA_DIR, REPORTS_DIR):
        folder.mkdir(parents=True, exist_ok=True)


@contextmanager
def stage_timer(logger, stage_name: str) -> Iterator[dict]:
    """
    Context manager that logs how long a pipeline stage took.

    Usage:
        with stage_timer(logger, "Ingestion") as timing:
            ...
        print(timing["seconds"])
    """
    timing = {"seconds": 0.0}
    logger.info("Starting stage: %s", stage_name)
    start = time.perf_counter()
    try:
        yield timing
    finally:
        timing["seconds"] = round(time.perf_counter() - start, 3)
        logger.info("Finished stage: %s in %.3f s", stage_name, timing["seconds"])


def dataframe_to_markdown(df: pd.DataFrame, max_rows: int = 30, float_format: str = "{:,.2f}") -> str:
    """
    Render a DataFrame as a GitHub style markdown table without extra libraries.

    Args:
        df: Data to render.
        max_rows: Rows beyond this limit are cut and a note is added.
        float_format: Format applied to float values.

    Returns:
        Markdown table as a string.
    """
    if df is None or df.empty:
        return "_No rows._\n"

    # object dtype stops iterrows from turning integer columns into floats
    shown = df.head(max_rows).astype(object)
    headers = [str(col) for col in shown.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]

    for _, row in shown.iterrows():
        cells = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                cells.append(float_format.format(value) if pd.notna(value) else "")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")

    if len(df) > max_rows:
        lines.append(f"\n_Showing {max_rows} of {len(df)} rows._")
    return "\n".join(lines) + "\n"


def write_json(payload: dict, path: Path) -> None:
    """Write a dictionary to disk as pretty printed JSON (numpy types handled)."""

    def _default(value):
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
        if isinstance(value, (np.bool_,)):
            return bool(value)
        return str(value)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=_default)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide two numbers and return a default instead of failing on zero."""
    if denominator in (0, None) or pd.isna(denominator):
        return default
    return numerator / denominator


def mode_with_tiebreak(series: pd.Series):
    """
    Most frequent value of a Series with a deterministic tie break.

    pandas .mode() can return several values on a tie. Here ties are broken
    alphabetically so the result never changes between runs.
    """
    clean = series.dropna()
    if clean.empty:
        return None
    counts = clean.value_counts()
    top_count = counts.max()
    return sorted(counts[counts == top_count].index.astype(str))[0]
