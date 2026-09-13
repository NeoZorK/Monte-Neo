# Professional bar backtest engine

Package: `monte_neo.backtest` (current line **v0.1.0**).

## Purpose

Fee-aware, next-bar **general-purpose bar research engine** with an explicit work
checklist for honest peer comparisons.

Use this package when you need matched execution semantics: fees, slippage,
optional impact, cash/position/equity, next-bar fills, SL/TP/trail, batch
sweeps, strategy specs, and a trade journal.

This is a **research bar engine**, not a full broker OMS (no L2 matching /
live gateway in this line).

## Frozen execution model (`ExecutionModel`)

| Field | Default | Meaning |
|-------|---------|---------|
| `fill_policy` | `next_bar_open` | Signal on bar `t` fills on bar `t+1` |
| `side_mode` | `long_flat` | Long/flat or long/short |
| `size_fraction` | `1.0` | Fraction of cash on entry |
| `fill_fraction` | `1.0` | Research-grade partial fill of intended size |
| `commission_bps` | `5.0` | Fee on fill notional |
| `slippage_bps` | `5.0` | Adverse price move on fills |
| `impact_bps` | `0.0` | Extra bps added to slippage |
| `sl_pct` / `tp_pct` | `0` | Stop / take-profit % of entry (0 = off) |
| `trail_pct` | `0` | Trailing stop % (0 = off) |
| `oco_bracket` | `True` | SL+TP treated as OCO when both set |

## Strategy expressions

```python
from monte_neo.backtest import ExecutionModel, StrategySpec, run_strategy_backtest

out = run_strategy_backtest(
    open_, high, low, close,
    StrategySpec(kind="sma_cross", fast=10, slow=40),
    model=ExecutionModel(sl_pct=1.0, tp_pct=2.0),
)
```

Kinds: `sma_cross`, `ema_cross`. External signal matrices use `run_bar_backtest` /
`run_bar_backtest_batch`.

## Testing

```bash
uv run pytest tests -n auto
```
