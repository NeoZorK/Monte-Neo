# Volatility-managed equity

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `vol_managed_mm`
- **type:** [Volatility targeting / managed portfolios](../TYPES.md#vol_managed)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Moreira Muir 2017 JF
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Scale monthly exposure by c / realized variance of previous month

Parameters (do not tune):

- `c` = set so average exposure is 1
- `window` = 1_month

**Data needed:** daily index returns

**Expected regime behaviour:** improves Sharpe when vol clusters

## Known traps

- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).

## How to measure

Metrics: Sharpe vs unmanaged, realized vol vs target, turnover, drawdown, leverage.
Benchmark: Same asset unmanaged and at matched average leverage.
Horizon: Includes vol-clustering episodes.

## What Monte-Neo cannot verify

- Gap risk between rebalances
