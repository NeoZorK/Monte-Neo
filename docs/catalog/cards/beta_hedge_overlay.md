# Beta-hedge overlay

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `beta_hedge_overlay`
- **type:** [Volatility targeting / managed portfolios](../TYPES.md#vol_managed)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Standard portfolio practice; Frazzini Pedersen 2014 for beta estimation
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Short index futures equal to the portfolio's 60-day beta times its value; rebalance weekly

Parameters (do not tune):

- `window` = 60
- `rebalance` = weekly

**Data needed:** portfolio returns, index futures

**Expected regime behaviour:** removes market exposure; betas jump in crashes

## Known traps

- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Execution timing** - Trade assumed at the close/open that generated the signal. Monte-Neo: lookahead, timing (existing).
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.

## How to measure

Metrics: Sharpe vs unmanaged, realized vol vs target, turnover, drawdown, leverage.
Benchmark: Same asset unmanaged and at matched average leverage.
Horizon: Includes vol-clustering episodes.

## What Monte-Neo cannot verify

- Gap risk between rebalances

## Worst scenario (hedged is not risk-free)

- **This strategy:** beta estimated in calm days is too low in a crash: the hedge is too small exactly when it is needed
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
