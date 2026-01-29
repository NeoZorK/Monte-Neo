#!/bin/bash

# Compilation script for Monte-Neo Metal Engine
# Requires: clang++, pybind11, macOS with Metal support

OUTPUT_DIR="src/monte_neo/core/acceleration/cpp_metal"
EXTENSION_NAME="metal_engine"
PYTHON_INCLUDES=$(python3 -m pybind11 --includes)
PYTHON_SUFFIX=$(python3-config --extension-suffix)

echo "🚀 Skipping Metal Shader library pre-compilation (will compile at runtime)..."
# xcrun -sdk macosx metal -c $OUTPUT_DIR/shaders/backtest_kernels.metal -o $OUTPUT_DIR/shaders/backtest_kernels.air
# xcrun -sdk macosx metallib $OUTPUT_DIR/shaders/backtest_kernels.air -o $OUTPUT_DIR/shaders/backtest_kernels.metallib
# rm $OUTPUT_DIR/shaders/backtest_kernels.air

echo "🚀 Compiling Swift Bridge..."
swiftc -c $OUTPUT_DIR/MetalBridgeSwift.swift -o $OUTPUT_DIR/MetalBridgeSwift.o -parse-as-library

echo "🚀 Compiling Metal Engine extension..."

clang++ -O3 -shared -std=c++17 -undefined dynamic_lookup \
    $PYTHON_INCLUDES \
    -I$OUTPUT_DIR/include \
    $OUTPUT_DIR/metal_bridge.mm \
    $OUTPUT_DIR/metal_metrics.mm \
    $OUTPUT_DIR/bindings.mm \
    $OUTPUT_DIR/MetalBridgeSwift.o \
    -o $OUTPUT_DIR/$EXTENSION_NAME$PYTHON_SUFFIX \
    -framework Metal -framework Foundation -framework QuartzCore -L/usr/lib/swift -lswiftCore -lswiftMetal -lswiftFoundation

if [ $? -eq 0 ]; then
    echo "✅ Successfully compiled $EXTENSION_NAME$PYTHON_SUFFIX"
else
    echo "❌ Compilation failed"
    exit 1
fi
