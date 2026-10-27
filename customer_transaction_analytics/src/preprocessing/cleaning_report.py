"""
Cleaning report.

Every cleaning step logs what it checked, how many rows it touched and what
action was taken. Rows that cannot be repaired are quarantined with a
reason instead of being silently dropped, which gives auditors a full trail.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.utils.config import PROCESSED_DATA_DIR, REPORTS_DIR
from src.utils.helpers import dataframe_to_markdown, write_json
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CleaningReport:
    """Collects cleaning steps and rejected records across all tables."""

    steps: List[dict] = field(default_factory=list)
    rejected_frames: List[pd.DataFrame] = field(default_factory=list)
    row_counts: Dict[str, dict] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #
    def log_step(self, table: str, check: str, rows_affected: int, action: str) -> None:
        """Record one cleaning check, even when it found nothing."""
        self.steps.append(
            {"table": table, "check": check, "rows_affected": int(rows_affected), "action": action}
        )
        if rows_affected:
            logger.info("[%s] %s: %d row(s) -> %s", table, check, rows_affected, action)

    def reject(self, table: str, rows: pd.DataFrame, key_column: str, reason: str) -> None:
        """Quarantine rows that cannot be repaired."""
        if rows.empty:
            return
        quarantined = pd.DataFrame(
            {
                "source_table": table,
                "record_key": rows[key_column].astype(str).values if key_column in rows else "",
                "reason": reason,
                "raw_record": [json.dumps(r, default=str) for r in rows.to_dict(orient="records")],
            }
        )
        self.rejected_frames.append(quarantined)

    def set_row_counts(self, table: str, rows_in: int, rows_out: int) -> None:
        """Store before and after row counts for a table."""
        self.row_counts[table] = {
            "rows_in": int(rows_in),
            "rows_out": int(rows_out),
            "rows_rejected": int(rows_in - rows_out),
        }

    # ------------------------------------------------------------------ #
    # Views
    # ------------------------------------------------------------------ #
    @property
    def rejected_records(self) -> pd.DataFrame:
        """All quarantined rows in one DataFrame."""
        if not self.rejected_frames:
            return pd.DataFrame(columns=["source_table", "record_key", "reason", "raw_record"])
        return pd.concat(self.rejected_frames, ignore_index=True)

    @property
    def steps_frame(self) -> pd.DataFrame:
        """Cleaning steps as a DataFrame."""
        return pd.DataFrame(self.steps, columns=["table", "check", "rows_affected", "action"])

    @property
    def summary_frame(self) -> pd.DataFrame:
        """Row counts per table as a DataFrame."""
        rows = [{"table": table, **counts} for table, counts in self.row_counts.items()]
        return pd.DataFrame(rows, columns=["table", "rows_in", "rows_out", "rows_rejected"])

    # ------------------------------------------------------------------ #
    # Output
    # ------------------------------------------------------------------ #
    def save(self, reports_dir: Path = REPORTS_DIR, processed_dir: Path = PROCESSED_DATA_DIR) -> None:
        """Write the report as Markdown and JSON, and the quarantine as CSV."""
        rejected = self.rejected_records
        rejected.to_csv(processed_dir / "rejected_records.csv", index=False)

        write_json(
            {
                "generated_at": self.generated_at,
                "row_counts": self.row_counts,
                "steps": self.steps,
                "rejected_record_count": len(rejected),
                "rejected_by_reason": rejected["reason"].value_counts().to_dict() if not rejected.empty else {},
            },
            reports_dir / "cleaning_report.json",
        )

        issues_found = self.steps_frame[self.steps_frame["rows_affected"] > 0]
        lines = [
            "# Data Cleaning Report",
            "",
            f"Generated: {self.generated_at}",
            "",
            "## Row counts per table",
            "",
            dataframe_to_markdown(self.summary_frame),
            "## Checks that found issues",
            "",
            dataframe_to_markdown(issues_found) if not issues_found.empty
            else "All checks passed. The source data had no issues for these rules.\n",
            "## Every check performed",
            "",
            dataframe_to_markdown(self.steps_frame, max_rows=200),
            "## Rejected (quarantined) records",
            "",
            f"Total rejected: {len(rejected)}. Full detail in `data/processed/rejected_records.csv`.",
            "",
            dataframe_to_markdown(rejected.drop(columns=["raw_record"]), max_rows=50)
            if not rejected.empty else "_No records were rejected._\n",
        ]
        (reports_dir / "cleaning_report.md").write_text("\n".join(lines), encoding="utf-8")
        logger.info("Cleaning report written to %s", reports_dir / "cleaning_report.md")
