# Quick Start

Export-first path: install → research export → optional policy triage → optional holdout.
The interactive CLI wizard is optional and documented at the bottom.

## 1. Install

```bash
pip install monte-neo
# Apple Silicon extras (MLX / Metal bindings):
pip install "monte-neo[apple]"
```

Isolated CLI: `pipx install "monte-neo[apple]"`.

Full matrix: [Installation](../setup/installation.md).

## 2. Export API (primary)

Fee-aware SMA sweep on synthetic OHLC — same shape as
[`examples/export_sma_sweep_quickstart.py`](https://github.com/NeoZorK/Monte-Neo/blob/main/examples/export_sma_sweep_quickstart.py):

```python
from monte_neo.backtest import ExecutionModel, export_sma_sweep, synthetic_ohlcv

ohlc = synthetic_ohlcv(100_000, seed=42)
model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=50)
out = export_sma_sweep(
    ohlc["open"],
    ohlc["high"],
    ohlc["low"],
    ohlc["close"],
    combos=16,
    model=model,
    device="auto",  # Metal when safe on Apple Silicon; else cpu_numba
)
print(
    {
        "device": out.get("device"),
        "fallback_reason": out.get("fallback_reason"),
        "combos": out.get("combos"),
        "ok": out.get("ok"),
    }
)
```

Aligned with the [Home](../index.md) snippet. More detail: [Research export API](../api/export.md).

## 3. Policy triage (optional)

After you save an `export_sma_sweep` / `export_batch` JSON:

```bash
monte-neo --policy-triage path/to/export.json
```

See [Research policy](../api/policy.md).

## 4. Holdout smoke (optional)

```bash
monte-neo --holdout-sma --holdout-bars 20000 --holdout-combos 32
```

See [Holdout](../api/holdout.md).

---

## CLI wizard (optional)

The interactive menu is still available if you prefer a guided loop.

```bash
uv run monte-neo
# or: monte-neo
```

Typical flow:

1. **Download Market Data** — searchable symbols (e.g. `BTCUSDT`), timeframe, history length
2. **Set Target Metrics** — e.g. profit factor threshold
3. **Generate Indicator** — search / optimize candidates

### Dynamic Mode (evolutionary)

1. In configuration, select `dynamic` among indicator types
2. Random search finds candidates first
3. With enough candidates, evolutionary optimization cross-breeds / mutates survivors
4. Results can be checked with Monte Carlo helpers

Tips: arrow keys navigate; Space toggles checkboxes.
Deep dive: [Dynamic Indicators](../project/dynamic_indicators.md).
