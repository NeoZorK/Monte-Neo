# Professional bar backtest engine

Package: `monte_neo.backtest` (first shipped in **v0.0.8**).

## Purpose

Fee-aware, next-bar bar engine with an explicit work checklist for honest peer
comparisons (ManifoldBT, vectorbt, backtesting.py, Nautilus, etc.).

This is **not** the ClaimBound D001 Type C specialized SMA kernel. D001 Type C
remains a specialized throughput gate. Use this engine when you need matched
semantics: fees, slippage, cash/position/equity, next-bar fills.

## Frozen execution model (`ExecutionModel`)

| Field | Default | Meaning |
|-------|---------|---------|
| `fill_policy` | `next_bar_open` | Signal on bar `t` fills on bar `t+1` open (or close) |
| `side_mode` | `long_flat` | Long/flat or long/short |
| `size_fraction` | `1.0` | Fraction of cash deployed on entry |
| `commission_bps` | `5.0` | Fee on each fill notional |
| `slippage_bps` | `5.0` | Adverse price move on fills |
| `initial_cash` | `100_000` | Starting cash |
| `warmup_bars` | `60` | No trading before this bar index |

Invariants:

- No same-bar fill (no lookahead into the fill bar’s future beyond the policy).
- Flatten at last close.
- `work_checklist` exposes what work was performed for peer honesty.

## API

```python
from monte_neo.backtest import (
    ExecutionModel,
    frame_to_ohlc,
    run_bar_backtest,
    run_sma_sweep,
    sma_signal,
    synthetic_ohlcv,
)

df = synthetic_ohlcv(5_000, seed=42)
ohlc = frame_to_ohlc(df)
model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, size_fraction=0.25)
sig = sma_signal(ohlc["close"], fast=10, slow=40)
out = run_bar_backtest(
    ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=model
)
sweep = run_sma_sweep(
    ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], combos=64, model=model
)
```

## Optional replay feeder

`ReplayBarSource` / `midprice_ticks_to_ohlc` convert in-memory bid/ask mid ticks
into OHLC **without Redis**. Redis belongs in integration tests, not in a
maximum-speed hot path against another bar engine.

## Testing

```bash
uv run pytest tests -n auto
```

Coverage for this module: unit + integration + stress + performance under
`tests/`.
