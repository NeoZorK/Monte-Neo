# Installation

## From PyPI (recommended)

```bash
pip install monte-neo
```

Apple Silicon extras (MLX + Metal Objective‑C bindings):

```bash
pip install "monte-neo[apple]"
```

Isolated CLI via pipx:

```bash
brew install pipx
pipx install "monte-neo[apple]"
```

Check:

```bash
monte-neo --version
python -c "import monte_neo; print(monte_neo.__version__)"
```

Current release: **v0.15.1** on [PyPI](https://pypi.org/project/monte-neo/).

## From source (developers)

```bash
git clone https://github.com/NeoZorK/Monte-Neo.git
cd Monte-Neo
uv sync
# optional native Metal extension:
uv run bash scripts/build_native.sh
```

See [Development setup](development-setup.md) and [Metal native build](../METAL_NATIVE_BUILD.md).

## Requirements

- **OS**: macOS Apple Silicon recommended for Metal; Linux/Windows OK for `cpu_numba` research path
- **Python**: 3.11+
- **Memory**: 8–16GB class hosts are the design center for large sweeps

## TestPyPI (maintainers only)

TestPyPI can contain stub packages that poison `--extra-index-url`. Prefer:

```bash
pip download --no-deps -d /tmp/mn-wheels --index-url https://test.pypi.org/simple/ monte-neo==0.15.1
pip install /tmp/mn-wheels/monte_neo-*.whl
# then install runtime deps from PyPI as needed, or use the real PyPI package
```

For everyday use, install from **PyPI**, not TestPyPI.
