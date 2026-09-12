#!/bin/bash
# Build all native extensions for the current uv/python environment.
# Run from repo root: uv run bash scripts/build_native.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$(command -v python)}"
export PYTHON

echo "=== Monte-Neo native build ==="
echo "Python: $PYTHON ($("$PYTHON" --version))"

"$PYTHON" -c "import setuptools" 2>/dev/null || {
    echo "Installing setuptools (required for pybind11 build on Python 3.13+)..."
    "$PYTHON" -m pip install setuptools
}

echo "--- native_metrics (pybind11) ---"
"$PYTHON" setup_native.py build_ext --inplace

echo "--- metal_engine (Metal C++/Swift) ---"
bash src/monte_neo/core/acceleration/cpp_metal/compile.sh

echo "--- verify imports ---"
"$PYTHON" - <<'PY'
import sysconfig

suffix = sysconfig.get_config_var("EXT_SUFFIX")
print(f"EXT_SUFFIX={suffix}")

import monte_neo.core.native_metrics as nm
print("native_metrics OK", nm)

from monte_neo.core.acceleration.cpp_metal.metal_engine import MetalBacktestBridge, Driver
bridge = MetalBacktestBridge(Driver.CPP)
ok = bridge.init()
print("MetalBacktestBridge init", ok)
PY

echo "=== native build complete ==="
