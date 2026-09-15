# Examples

| Script | What it shows |
|--------|----------------|
| `export_sma_sweep_quickstart.py` | Fee-aware research export on synthetic bars (`device="auto"`) |

```bash
uv run python examples/export_sma_sweep_quickstart.py
```

On Apple Silicon, for Metal/MLX installs from a future PyPI wheel use:

```bash
pip install "monte-neo[apple]"
```

Until PyPI: install from git / this repo (`uv sync`).
