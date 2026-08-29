# Native extensions (Metal / pybind11)

Monte-Neo ships two optional native layers on macOS with Apple Silicon:

| Extension | Module | Role |
|---|---|---|
| `native_metrics` | `monte_neo.core.native_metrics` | Fast trade extraction (pybind11) |
| `metal_engine` | `monte_neo.core.acceleration.cpp_metal.metal_engine` | Metal GPU bar-loop backtest |

A third path, `MetalFloat8Engine` (`monte_neo.core.native.metal_engine`), uses pyobjc + `.metal` shaders and does not require compiling `metal_engine`.

## Root cause of "Metal dead" on Python 3.13

Extensions must match the **same Python ABI** as the runtime interpreter.

Failure mode observed:

- `native_metrics.cpython-314-darwin.so` and `metal_engine.cpython-314-darwin.so` built while system `python3-config` pointed at 3.14
- Project venv runs **Python 3.13** → `ModuleNotFoundError`

`compile.sh` previously used `python3-config --extension-suffix` from PATH instead of the active venv Python.

## Build (recommended)

From repo root, with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run bash scripts/build_native.sh
```

This builds both extensions for the current interpreter and verifies imports.

Requirements: macOS, Xcode/clang, Swift, Metal, pybind11 (installed via uv).

## Manual build

```bash
export PYTHON="$(pwd)/.venv/bin/python"
uv run python setup_native.py build_ext --inplace
bash src/monte_neo/core/acceleration/cpp_metal/compile.sh
```

## Verify

```bash
uv run python verify_hardware.py
uv run pytest tests -k metal -n auto
```

## Notes

- `.so` files are gitignored; every clone must run `scripts/build_native.sh` once.
- Python 3.13+ requires `setuptools` for `setup_native.py` (included in dev workflow via build script).
- Do not mix extension suffixes (e.g. 3.14 `.so` with 3.13 runtime).
