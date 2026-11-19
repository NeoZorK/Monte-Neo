# Volatility target 10%

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `vol_target_10`
- **type:** [Volatility targeting / managed portfolios](../TYPES.md#vol_managed)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Harvey et al. 2018 JPM
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Exposure = 10% / 20-day realized vol, capped at 2x

Parameters (do not tune):

- `target` = 0.1
- `window` = 20
- `cap` = 2.0

**Data needed:** daily returns

**Expected regime behaviour:** reduces left tail in equities

## Known traps

- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.
- **Execution timing** - Trade assumed at the close/open that generated the signal. Monte-Neo: lookahead, timing (existing).
- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.

## How to measure

Metrics: Sharpe vs unmanaged, realized vol vs target, turnover, drawdown, leverage.
Benchmark: Same asset unmanaged and at matched average leverage.
Horizon: Includes vol-clustering episodes.

## What Monte-Neo cannot verify

- Gap risk between rebalances
