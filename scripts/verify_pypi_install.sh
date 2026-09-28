#!/usr/bin/env bash
# Smoke: install monte-neo from PyPI into a clean venv and run the product the way a user does.
# Usage: ./scripts/verify_pypi_install.sh [version]     (no version = latest on PyPI)
# Example: ./scripts/verify_pypi_install.sh 0.32.0
# Handles PyPI CDN lag with retries/sleeps.
set -euo pipefail
VER="${1:-}"
VER="${VER#v}"
SPEC="monte-neo[sign]"
if [ -n "$VER" ]; then SPEC="monte-neo[sign]==${VER}"; fi
DIR="$(mktemp -d)"
trap 'rm -rf "$DIR"' EXIT
python3 -m venv "$DIR/venv"
"$DIR/venv/bin/pip" install -q --upgrade pip

MAX_ATTEMPTS="${VERIFY_PYPI_MAX_ATTEMPTS:-8}"
SLEEP_SECS="${VERIFY_PYPI_SLEEP_SECS:-20}"
attempt=1
while true; do
  if "$DIR/venv/bin/pip" install -q --no-cache-dir "$SPEC"; then
    break
  fi
  if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    echo "verify_pypi_install: failed to install ${SPEC} after ${MAX_ATTEMPTS} attempts" >&2
    exit 1
  fi
  echo "verify_pypi_install: attempt ${attempt}/${MAX_ATTEMPTS} failed (CDN lag?); sleeping ${SLEEP_SECS}s..."
  sleep "$SLEEP_SECS"
  attempt=$((attempt + 1))
done

BIN="$DIR/venv/bin"
cd "$DIR"
"$BIN/monte-neo" --version

# Data and strategies: a leak (must be REJECT) and an honest SMA cross.
"$BIN/python" -c "
from monte_neo.backtest import synthetic_ohlcv
synthetic_ohlcv(3000, seed=1).to_csv('prices.csv', index=False)
"
printf 'import numpy as np\n\ndef signal(df):\n    return np.sign(df["close"].shift(-1) - df["close"])\n' > leaky.py
printf 'def signal(df, fast=10, slow=40):\n    c = df["close"]\n    return (c.rolling(fast).mean() > c.rolling(slow).mean()).astype(int)\n' > sma.py

set +e
"$BIN/monte-neo" verify --ohlcv prices.csv --strategy leaky.py --out cert.json --format json > /dev/null
code=$?
set -e
test "$code" -eq 2 || { echo "verify_pypi_install: leaky strategy exit $code, expected 2 (REJECT)" >&2; exit 1; }
"$BIN/monte-neo" verify --recheck cert.json --ohlcv prices.csv --strategy leaky.py > /dev/null
"$BIN/monte-neo" verify --ohlcv prices.csv --strategy sma.py --grid '{"fast": [5, 10], "slow": [40]}' > /dev/null || true

"$BIN/monte-neo" verify --keygen k > /dev/null
"$BIN/monte-neo" verify --ohlcv prices.csv --strategy sma.py --sign k.key --out signed.json > /dev/null || true
"$BIN/monte-neo" verify --check-signature signed.json --public-key k.pub > /dev/null

"$BIN/monte-neo" bench init hb --bars 400 > /dev/null
"$BIN/monte-neo" bench prepare hb --agents smoke --workspaces ws > /dev/null
cp sma.py ws/smoke/task-1/strategy.py
"$BIN/monte-neo" bench collect hb --workspaces ws > /dev/null
"$BIN/monte-neo" bench hb > /dev/null

"$BIN/python" - <<'PY'
import json
from monte_neo.mcp import tools
from monte_neo.mcp.server import build_server

build_server()  # the MCP SDK is a default dependency
names = sorted(fn.__name__ for fn in tools.TOOLS)
assert {"verify_strategy", "check_signature", "recheck_certificate"} <= set(names), names
assert json.load(open("cert.json"))["verdict"] == "REJECT"
print("mcp tools:", ", ".join(names))
PY
echo "verify_pypi_install: ${SPEC} OK"
