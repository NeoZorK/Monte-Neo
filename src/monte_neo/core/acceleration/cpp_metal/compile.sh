#!/bin/bash
# Compile Metal backtest pybind11 extension for the active Python interpreter.
# Usage: PYTHON=/path/to/python bash compile.sh

set -euo pipefail

OUTPUT_DIR="src/monte_neo/core/acceleration/cpp_metal"
EXTENSION_NAME="metal_engine"
PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "❌ Python not found: $PYTHON"
    exit 1
fi

PYTHON_INCLUDES=($("$PYTHON" -m pybind11 --includes))
PYTHON_SUFFIX=$("$PYTHON" -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))")

echo "🐍 Using $PYTHON ($("$PYTHON" --version))"
echo "📦 Extension suffix: $PYTHON_SUFFIX"

echo "🚀 Skipping Metal Shader library pre-compilation (will compile at runtime)..."

echo "🚀 Compiling Swift Bridge..."
swiftc -c "$OUTPUT_DIR/MetalBridgeSwift.swift" -o "$OUTPUT_DIR/MetalBridgeSwift.o" -parse-as-library

echo "🚀 Compiling Metal Engine extension..."

clang++ -O3 -shared -std=c++17 -undefined dynamic_lookup \
    "${PYTHON_INCLUDES[@]}" \
    -I"$OUTPUT_DIR/include" \
    "$OUTPUT_DIR/metal_bridge.mm" \
    "$OUTPUT_DIR/metal_metrics.mm" \
    "$OUTPUT_DIR/bindings.mm" \
    "$OUTPUT_DIR/MetalBridgeSwift.o" \
    -o "$OUTPUT_DIR/$EXTENSION_NAME$PYTHON_SUFFIX" \
    -framework Metal -framework Foundation -framework QuartzCore \
    -L/usr/lib/swift -lswiftCore -lswiftMetal -lswiftFoundation

echo "✅ Successfully compiled $EXTENSION_NAME$PYTHON_SUFFIX"
