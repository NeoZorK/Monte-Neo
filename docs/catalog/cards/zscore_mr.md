# Z-score mean reversion

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `zscore_mr`
- **type:** [Short-term mean reversion (single instrument)](../TYPES.md#mean_reversion)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Standard statistical rule (textbook)
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long z < -2, exit z > 0, where z uses 20-day mean and std

Parameters (do not tune):

- `window` = 20
- `entry` = 2.0
- `exit` = 0.0

**Data needed:** daily close

**Expected regime behaviour:** stationary prices only

## Known traps

- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).

## How to measure

Metrics: Win rate, payoff ratio, expectancy per trade, max adverse excursion, tail loss, time in market.
Benchmark: Buy-and-hold and a random-entry null with the same holding time.
Horizon: Many independent trades; drawdown clustered in trends.

## What Monte-Neo cannot verify

- Intraday excursion beyond daily bars
