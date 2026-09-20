"""Reporting helpers: named test steps that show up in logs and in the Allure report."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from utils.logger import get_logger

try:
    import allure
except ImportError:  # Allure is optional
    allure = None

_log = get_logger("step")


@contextmanager
def step(title: str) -> Iterator[None]:
    _log.info("========== STEP: %s ==========", title)
    if allure is not None:
        with allure.step(title):
            yield
    else:
        yield


def attach_png(image: bytes, name: str) -> None:
    """Attach an image to the Allure report (no-op when Allure is not installed)."""
    if allure is not None:
        allure.attach(image, name=name, attachment_type=allure.attachment_type.PNG)
