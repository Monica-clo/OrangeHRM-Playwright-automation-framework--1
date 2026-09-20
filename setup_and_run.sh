#!/usr/bin/env bash
# =============================================================================
#  OrangeHRM automation - setup and run (macOS / Linux)
#
#      ./setup_and_run.sh              # setup, then run API + UI + performance
#      ./setup_and_run.sh api          # API contract suite only (no browser)
#      ./setup_and_run.sh ui           # 5 E2E workflows only
#      ./setup_and_run.sh perf         # k6 performance only
#      ./setup_and_run.sh setup        # create the venv and install, run nothing
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")"

ONLY="${1:-all}"
BROWSER="${BROWSER:-chromium}"

cyan()  { printf '\n\033[36m=== %s ===\033[0m\n' "$1"; }
ok()    { printf '\033[32m  %s\033[0m\n' "$1"; }
warn()  { printf '\033[33m  %s\033[0m\n' "$1"; }

[ -f pytest.ini ] || { echo "Run this from the project folder (the one with pytest.ini)."; exit 1; }

cyan "Virtual environment"
if [ -x .venv/bin/python ]; then ok "Reusing the existing .venv"; else
  rm -rf .venv; python3 -m venv .venv; ok "Created .venv"
fi
PY=".venv/bin/python"
ok "Python: $($PY --version)"

cyan "Dependencies"
$PY -m pip install --upgrade pip --quiet
$PY -m pip install -r requirements.txt --quiet
ok "Python packages installed"
$PY -m playwright install --with-deps "$BROWSER"
ok "Playwright browser '$BROWSER' ready"

mkdir -p reports/performance reports/junit reports/html
[ "$ONLY" = "setup" ] && { cyan "Setup complete - nothing was run"; exit 0; }

FAILED=()

if [ "$ONLY" = "all" ] || [ "$ONLY" = "api" ]; then
  cyan "1/3  API contract tests (ReqRes - no browser)"
  $PY -m pytest -m api \
      --html=reports/html/api-report.html \
      --junitxml=reports/junit/api-results.xml || FAILED+=("api")
fi

if [ "$ONLY" = "all" ] || [ "$ONLY" = "ui" ]; then
  cyan "2/3  E2E workflows - UI + API hybrid ($BROWSER)"
  warn "Drives a real browser against the OrangeHRM demo site; takes several minutes."
  $PY -m pytest -m workflow --browser "$BROWSER" \
      --html=reports/html/e2e-report.html \
      --junitxml=reports/junit/e2e-results.xml || FAILED+=("ui")
fi

if [ "$ONLY" = "all" ] || [ "$ONLY" = "perf" ]; then
  cyan "3/3  k6 performance (login API + employee creation API)"
  K6="${K6_BIN:-k6}"
  if command -v "$K6" >/dev/null 2>&1; then
    ok "Using k6: $K6"
    "$K6" run performance/k6/api-performance.js || FAILED+=("perf")
  else
    warn "k6 not found. Install it (brew install k6 / see k6.io/docs) or set K6_BIN."
    FAILED+=("perf (k6 missing)")
  fi
fi

cyan "Summary"
if [ ${#FAILED[@]} -eq 0 ]; then ok "All requested suites passed."; else
  warn "Suites that did not pass: ${FAILED[*]}"
fi
echo
echo "  reports/html/api-report.html         API contract results"
echo "  reports/html/e2e-report.html         UI workflow results (videos embedded)"
echo "  reports/performance/k6-report.html   k6 performance results"
echo
[ ${#FAILED[@]} -eq 0 ] || exit 1
