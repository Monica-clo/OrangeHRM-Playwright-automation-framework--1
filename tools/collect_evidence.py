"""Copy the latest HTML report(s), videos and screenshots into evidence/ so they can be committed.

The assessment asks for the HTML report and the test-run video in the repository.
reports/ is git-ignored (it changes on every run), so run this after a successful run:

    python tools/collect_evidence.py
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
EVIDENCE = ROOT / "evidence"


def main() -> int:
    if not REPORTS.is_dir():
        print("No reports/ folder found - run the tests first: python -m pytest")
        return 1
    target = EVIDENCE / datetime.now().strftime("run_%Y-%m-%d_%H-%M")
    for folder in ("html", "videos", "screenshots", "performance"):
        source = REPORTS / folder
        if source.is_dir() and any(source.rglob("*")):
            shutil.copytree(source, target / folder, dirs_exist_ok=True)
    (EVIDENCE / "LATEST.txt").parent.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "LATEST.txt").write_text(f"{target.name}\n", encoding="utf-8")
    videos = list((target / "videos").rglob("*.webm")) if (target / "videos").is_dir() else []
    print(f"Evidence copied to {target.relative_to(ROOT)}  ({len(videos)} video file(s))")
    print("Open the report from inside that folder so the embedded videos play.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
