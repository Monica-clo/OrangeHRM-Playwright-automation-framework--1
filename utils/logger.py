"""Framework logger - writes to the console (pytest live logs) and reports/logs/test_run.log."""
from __future__ import annotations

import logging
import os

from config.settings import settings

_ROOT_LOGGER_NAME = "orangehrm"
_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.setLevel(logging.INFO)
    worker = os.getenv("PYTEST_XDIST_WORKER", "main")        # gw0, gw1 ... when running with -n
    log_name = "test_run.log" if worker == "main" else f"test_run_{worker}.log"
    file_handler = logging.FileHandler(settings.logs_dir / log_name, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter(f"%(asctime)s | {worker} | %(levelname)-7s | %(name)s | %(message)s")
    )
    root.addHandler(file_handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
