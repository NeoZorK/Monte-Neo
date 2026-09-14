# Professional bar backtest engine

Package: `monte_neo.backtest` (research lane; current line **v0.7.0**).

## Purpose

Fee-aware, next-bar **general-purpose bar research engine** with an explicit work
checklist for honest peer comparisons.

Use this package when you need matched execution semantics: fees, slippage,
optional impact, cash/position/equity, next-bar fills, SL/TP/trail, funding,
leverage, session masks, batch sweeps, strategy specs, shared-cash portfolio,
and a trade journal.

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
| `oco_bracket` | `True` | SL preferred when SL+TP both hit same bar |
| `leverage` | `1.0` | Scales entry notional (`>= 1`) |
| `funding_bps_per_bar` | `0.0` | Cash debit per bar while holding |

Optional call arg: `session_mask` (bool array) — blocks **new entries** off-session;
exits and SL/TP/trail still apply.

## APIs

```python
from monte_neo.backtest import (
    ExecutionModel,
    StrategySpec,
    run_strategy_backtest,
    run_portfolio_shared_cash,
)

out = run_strategy_backtest(
    open_, high, low, close,
    StrategySpec(kind="sma_cross", fast=10, slow=40),
    model=ExecutionModel(sl_pct=1.0, tp_pct=2.0, leverage=1.0),
    session_mask=mask,  # optional
)

port = run_portfolio_shared_cash(books, signals, model=ExecutionModel(size_fraction=0.4))
```

Also: `run_bar_backtest`, `run_bar_backtest_batch`, `run_sma_sweep`,
`run_multi_symbol_lite` (independent cash books).

## Testing

```bash
uv run pytest tests -n auto
```

## Scope honesty

Matched bar-research semantics for private local races. Public ClaimBound speed
evidence is gated until an honest top-10 speed win (see project roadmap / plan).
