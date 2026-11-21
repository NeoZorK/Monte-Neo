# Averaging down without stop

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `averaging_down_control`
- **type:** [Negative controls and null strategies](../TYPES.md#controls)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Retail practice; CONTROL
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Buy an equal amount every 5% fall from the first entry, sell all at 3% above the average price

Parameters (do not tune):

- `step` = 0.05
- `target` = 0.03

**Data needed:** daily OHLCV

**Expected regime behaviour:** CONTROL: works until a coin goes to zero

## Known traps

- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.

## How to measure

Metrics: Verdict distribution, false-positive rate of the verifier.
Benchmark: Verifier expectation (should not PASS).
Horizon: Same as the catalog.

## What Monte-Neo cannot verify

- Nothing special; they exist to measure verifier calibration
