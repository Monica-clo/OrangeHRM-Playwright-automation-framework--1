#!/usr/bin/env bash
# Usage: ./run_tests.sh [api|workflow|positive|negative|smoke|regression|perf] [extra pytest / k6 options]
#   ./run_tests.sh                    -> all 5 E2E workflows (UI + API)
#   ./run_tests.sh api                -> API-only contract suite (no browser)
#   ./run_tests.sh negative           -> the negative workflow only
#   ./run_tests.sh positive --headed  -> the 4 positive workflows with a visible browser
#   ./run_tests.sh perf               -> k6 performance test (login + employee creation API)
set -euo pipefail
cd "$(dirname "$0")"
[ -f .venv/bin/activate ] && source .venv/bin/activate
case "${1:-}" in
  perf)
    shift
    mkdir -p reports/performance
    # k6 comes from PATH; K6_BIN lets you point at an installed copy instead.
    "${K6_BIN:-k6}" run "$@" performance/k6/api-performance.js ;;
  api|workflow|positive|negative|smoke|regression)
    marker="$1"; shift
    python -m pytest -m "$marker" "$@" ;;
  *)
    python -m pytest -m workflow "$@" ;;
esac
