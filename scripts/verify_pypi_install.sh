#!/usr/bin/env bash
# Smoke: install monte-neo from PyPI into a temp venv and import policy/holdout.
# Usage: ./scripts/verify_pypi_install.sh [version]
# Example: ./scripts/verify_pypi_install.sh 0.17.1
set -euo pipefail
VER="${1:-0.17.1}"
DIR="$(mktemp -d)"
trap 'rm -rf "$DIR"' EXIT
python3 -m venv "$DIR/venv"
"$DIR/venv/bin/pip" install -q --upgrade pip
"$DIR/venv/bin/pip" install -q "monte-neo==${VER}"
"$DIR/venv/bin/python" -c "
import monte_neo
from monte_neo.policy import triage_export
from monte_neo.backtest import holdout_sma_sweep
print(monte_neo.__version__)
assert triage_export is not None and holdout_sma_sweep is not None
"
echo "verify_pypi_install: monte-neo==${VER} OK"
