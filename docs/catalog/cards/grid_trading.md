# Grid trading (negative control)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `grid_trading`
- **type:** [Negative controls and null strategies](../TYPES.md#controls)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Retail practice; no academic source
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Buy at fixed price steps below, sell steps above

Parameters (do not tune):

- `step_pct` = 1.0
- `levels` = 10

**Data needed:** daily or intraday

**Expected regime behaviour:** looks stable until a trend

## Known traps

- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.

## How to measure

Metrics: Verdict distribution, false-positive rate of the verifier.
Benchmark: Verifier expectation (should not PASS).
Horizon: Same as the catalog.

## What Monte-Neo cannot verify

- Nothing special; they exist to measure verifier calibration
