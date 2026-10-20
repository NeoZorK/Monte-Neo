# Examples

| Script | What it shows |
|--------|----------------|
| `export_sma_sweep_quickstart.py` | Fee-aware research export on synthetic bars (`device="auto"`) |
| `ml_fit_predict.py` | Ridge model in the fit/predict protocol; prints the verdict and the `ml_refit_gap` row (a LightGBM model drops into `fit` the same way) |
| `llm_news_signal.py` | News-sentiment strategy on events joined by publication time, with `model_cutoff`; prints the `pit_events` and `model_cutoff` rows |
| `phantom_pairs/` | Phantom profit: a pairs rule with a rolling hedge booked wrongly and correctly, a legs file generator and the strategies for `verify --null-test` |
| `allocator_dd.py` | Allocator due diligence: `verify_returns` on three demo managers, printed as a table |

```bash
uv run python examples/export_sma_sweep_quickstart.py
```

On Apple Silicon, for Metal/MLX installs from a future PyPI wheel use:

```bash
pip install "monte-neo[apple]"
```

Until PyPI: install from git / this repo (`uv sync`).
