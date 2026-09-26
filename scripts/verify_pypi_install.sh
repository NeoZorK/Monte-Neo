#!/usr/bin/env bash
# Smoke: install monte-neo from PyPI into a temp venv and import policy/holdout.
# Usage: ./scripts/verify_pypi_install.sh [version]
# Example: ./scripts/verify_pypi_install.sh 0.18.0
# Handles PyPI CDN lag with retries/sleeps.
set -euo pipefail
VER="${1:-0.18.0}"
VER="${VER#v}"
DIR="$(mktemp -d)"
trap 'rm -rf "$DIR"' EXIT
python3 -m venv "$DIR/venv"
"$DIR/venv/bin/pip" install -q --upgrade pip

MAX_ATTEMPTS="${VERIFY_PYPI_MAX_ATTEMPTS:-8}"
SLEEP_SECS="${VERIFY_PYPI_SLEEP_SECS:-20}"
attempt=1
while true; do
  if "$DIR/venv/bin/pip" install -q --no-cache-dir "monte-neo==${VER}"; then
    break
  fi
  if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    echo "verify_pypi_install: failed to install monte-neo==${VER} after ${MAX_ATTEMPTS} attempts" >&2
    exit 1
  fi
  echo "verify_pypi_install: attempt ${attempt}/${MAX_ATTEMPTS} failed (CDN lag?); sleeping ${SLEEP_SECS}s..."
  sleep "$SLEEP_SECS"
  attempt=$((attempt + 1))
done

"$DIR/venv/bin/python" -c "
import monte_neo
from monte_neo.policy import triage_export
from monte_neo.backtest import holdout_sma_sweep
print(monte_neo.__version__)
assert triage_export is not None and holdout_sma_sweep is not None
"
echo "verify_pypi_install: monte-neo==${VER} OK"
