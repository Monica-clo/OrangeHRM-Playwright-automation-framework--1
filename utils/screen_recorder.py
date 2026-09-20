"""UI screen recording helpers.

* Every UI test is recorded by the browser context (see conftest.py).
* The finished video is saved as reports/videos/<test name>.webm.
* ScreenRecorder shows a caption with the current step on top of the page,
  so the recording explains itself when you watch it later.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from config.settings import settings
from utils.logger import get_logger
from utils.reporting import step as report_step

_log = get_logger("screen_recorder")
_CAPTION_KEY = "__qa_recording_caption__"

# Defines window.__qaSetCaption and restores the caption after every navigation.
# pointer-events:none -> the caption never blocks clicks.
CAPTION_FUNCTION = """() => {
  const KEY = '%(key)s';
  const render = (text) => {
    if (!document.body) return;
    let el = document.getElementById(KEY);
    if (!text) { if (el) el.remove(); return; }
    if (!el) {
      el = document.createElement('div');
      el.id = KEY;
      Object.assign(el.style, {
        position: 'fixed', top: '8px', left: '50%%', transform: 'translateX(-50%%)',
        zIndex: '2147483647', pointerEvents: 'none', maxWidth: '80%%', textAlign: 'center',
        background: 'rgba(17, 24, 39, 0.88)', color: '#ffffff', padding: '6px 16px',
        borderRadius: '8px', font: '600 14px/1.4 Arial, Helvetica, sans-serif',
        boxShadow: '0 2px 8px rgba(0,0,0,.35)'
      });
      document.body.appendChild(el);
    }
    el.textContent = text;
  };
  window.__qaSetCaption = (text) => {
    try { sessionStorage.setItem(KEY, text || ''); } catch (e) {}
    render(text);
  };
  const restore = () => { try { render(sessionStorage.getItem(KEY)); } catch (e) {} };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', restore);
  else restore();
}""" % {"key": _CAPTION_KEY}
CAPTION_INIT_SCRIPT = f"({CAPTION_FUNCTION})();"


def video_file_for(test_name: str) -> Path:
    """Final, human-readable video path for a test."""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", test_name).strip("_")[:120]
    return settings.videos_dir / f"{safe}.webm"


class ScreenRecorder:
    """Adds on-screen step captions to the recorded video of a test."""

    def __init__(self, page: Page, test_name: str) -> None:
        self.page = page
        self.test_name = test_name
        self.enabled = page.video is not None   # False when recording is off or unsupported
        self.video_file: Optional[Path] = video_file_for(test_name) if self.enabled else None
        if self.enabled and settings.video_captions:
            page.add_init_script(CAPTION_INIT_SCRIPT)
        _log.info(
            "Screen recording %s for '%s'%s",
            "ON" if self.enabled else "OFF",
            test_name,
            f" -> {self.video_file}" if self.video_file else "",
        )

    def caption(self, text: str) -> None:
        """Show `text` on top of the page (visible in the video)."""
        if not (self.enabled and settings.video_captions):
            return
        try:
            if not self.page.evaluate("() => typeof window.__qaSetCaption === 'function'"):
                self.page.evaluate(CAPTION_FUNCTION)
            self.page.evaluate("text => window.__qaSetCaption(text)", text)
        except PlaywrightError as error:  # page navigating - the init script restores it
            _log.debug("Caption not shown yet (%s)", error)

    @contextmanager
    def step(self, title: str) -> Iterator[None]:
        """Report step + on-screen caption in one call."""
        self.caption(title)
        with report_step(title):
            yield

    def clear(self) -> None:
        self.caption("")
