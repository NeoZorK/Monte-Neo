#!/bin/bash -eu
# Install the package and compile every fuzz_*.py target next to this script into a standalone fuzzer.
# Dependencies come from the hash-locked runtime lock; the package itself is an editable install that resolves nothing (Scorecard counts --no-deps -e as pinned).
pip3 install --require-hashes --no-deps -r scripts/requirements/runtime.txt
pip3 install --no-deps -e .
for fuzzer in $(find "$SRC/monte-neo/.clusterfuzzlite" -name 'fuzz_*.py'); do
  compile_python_fuzzer "$fuzzer"
done
