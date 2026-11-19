#!/bin/bash -eu
# Install the package and compile every fuzz_*.py target next to this script into a standalone fuzzer.
pip3 install .
for fuzzer in $(find "$SRC/monte-neo/.clusterfuzzlite" -name 'fuzz_*.py'); do
  compile_python_fuzzer "$fuzzer"
done
