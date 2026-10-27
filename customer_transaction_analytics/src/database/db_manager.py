"""
SQLite connection management.

Small wrapper around the standard library sqlite3 module so every caller
opens connections the same way (foreign keys on, row factory set) and SQL
scripts are executed from files rather than strings in Python code.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

from src.utils.config import DATABASE_PATH
from src.utils.logger import get_logger

logger = get_logger(__name__)


@contextmanager
def get_connection(db_path: Path = DATABASE_PATH, read_only: bool = False) -> Iterator[sqlite3.Connection]:
    """
    Open a SQLite connection that is always closed afterwards.

    Args:
        db_path: Location of the database file.
        read_only: Open in read only mode (used by the dashboard).

    Yields:
        sqlite3.Connection with foreign key enforcement switched on.
    """
    if read_only:
        if not Path(db_path).exists():
            raise FileNotFoundError(f"Database not found at {db_path}. Run 'python main.py' first.")
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    else:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON;")
    try:
        yield connection
        if not read_only:
            connection.commit()
    except Exception:
        if not read_only:
            connection.rollback()
        raise
    finally:
        connection.close()


def execute_sql_file(connection: sqlite3.Connection, sql_path: Path) -> None:
    """Run every statement in a .sql file."""
    script = Path(sql_path).read_text(encoding="utf-8")
    connection.executescript(script)
    # executescript resets pragmas in some builds, so switch FK checks back on
    connection.execute("PRAGMA foreign_keys = ON;")
    logger.info("Executed SQL script %s", Path(sql_path).name)


def query_to_dataframe(
    connection: sqlite3.Connection, sql: str, params: Optional[dict] = None
) -> pd.DataFrame:
    """Run a SELECT statement and return the result as a DataFrame."""
    return pd.read_sql_query(sql, connection, params=params or {})


def table_row_counts(connection: sqlite3.Connection) -> pd.DataFrame:
    """Row count of every user table, used for the load summary."""
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    rows = [
        {"table": name, "rows": connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]}
        for (name,) in tables
    ]
    return pd.DataFrame(rows)
