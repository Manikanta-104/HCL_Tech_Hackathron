"""
Logging helper.

All modules call get_logger(__name__) so every message carries the module
name and lands in both the console and reports/pipeline_run.log.
"""

import logging
import sys

from src.utils.config import LOG_FILE_PATH, REPORTS_DIR

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_configured = False


def _configure_root_logger() -> None:
    """Attach a console handler and a file handler to the project logger once."""
    global _configured
    if _configured:
        return

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    project_logger = logging.getLogger("cta")
    project_logger.setLevel(logging.INFO)
    project_logger.propagate = False

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    project_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(LOG_FILE_PATH, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    project_logger.addHandler(file_handler)

    _configured = True


def get_logger(module_name: str) -> logging.Logger:
    """
    Return a child logger of the project logger.

    Args:
        module_name: Usually __name__ of the calling module.

    Returns:
        A configured logging.Logger instance.
    """
    _configure_root_logger()
    short_name = module_name.replace("src.", "")
    return logging.getLogger(f"cta.{short_name}")
