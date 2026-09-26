# Installation

## From PyPI (recommended)

```bash
pip install monte-neo                 # research-core (slim)
pip install "monte-neo[apple]"        # Metal / MLX (Apple Silicon macOS)
```

Check:

```bash
monte-neo --version
python -c "import monte_neo; print(monte_neo.__version__)"
```

Current release: **v0.20.0** on [PyPI](https://pypi.org/project/monte-neo/).

Docs site: [neozork.github.io/Monte-Neo](https://neozork.github.io/Monte-Neo/).

Maintainer smoke (clean venv + import policy/holdout): `./scripts/verify_pypi_install.sh [version]` — also run by CI workflow **PyPI install smoke** (weekly / dispatch / on release).

## Isolated CLI (pipx)

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install "monte-neo[apple]"       # or: pipx install monte-neo
monte-neo --version
```

`brew install pipx` also works if you already use Homebrew — not required.

## Optional extras

| Extra | When |
|-------|------|
| `apple` | Metal / MLX on **macOS** (`sys_platform == 'darwin'`) |
| `plot` | Charts / visualization helpers |
| `data` | Binance downloader / websocket |
| `ml` | LightGBM / sklearn / scipy / ta |
| `server` | FastAPI / redis / postgres client |
| `full` | Kitchen-sink local parity with pre-0.16 installs |
| `dev` | Pytest stack (+ plot/data/scipy for CI) |

```bash
pip install "monte-neo[plot]"
pip install "monte-neo[data]"
pip install "monte-neo[full]"
```

Missing plot/data imports raise a clear “install monte-neo[…]” error.

## From source (developers)

```bash
git clone https://github.com/NeoZorK/Monte-Neo.git
cd Monte-Neo
uv sync --extra apple --extra plot --extra data --group dev
# optional native Metal extension:
uv run bash scripts/build_native.sh
```

See [Development setup](development-setup.md), [Contributing](../development/contributing.md), and [Metal native build](../METAL_NATIVE_BUILD.md).

## Requirements

- **OS**: macOS Apple Silicon recommended for Metal; Linux OK for `cpu_numba` research path
- **Python**: 3.11+
- **Memory**: 8–16GB-class hosts are the design center for large sweeps

## TestPyPI (maintainers only)

**Do not** use `--extra-index-url https://test.pypi.org/simple/` for normal installs — stub packages on TestPyPI can poison dependency resolution.

Safe rehearsal:

```bash
# download the wheel only from TestPyPI, install without resolving deps there
pip download --no-deps -d /tmp/mn-wheels \
  --index-url https://test.pypi.org/simple/ \
  monte-neo==0.20.0
pip install --no-deps /tmp/mn-wheels/monte_neo-*.whl
# runtime deps still come from real PyPI:
pip install numpy pandas pyarrow numba rich questionary prompt-toolkit pyyaml python-dotenv pybind11
```

Everyday users: install from **PyPI**, not TestPyPI.

See [PACKAGING.md](../project/PACKAGING.md) for OIDC Trusted Publishing.
