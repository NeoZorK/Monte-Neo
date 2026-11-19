# Weekly short straddle

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `short_straddle`
- **type:** [Volatility selling / short vol](../TYPES.md#short_volatility)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Coval Shumway 2001 (return evidence)
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Sell ATM straddle each Monday, hold to Friday

Parameters (do not tune):

- `tenor` = 1 week

**Data needed:** option chains

**Expected regime behaviour:** VRP harvest

## Known traps

- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Return smoothing / stale marks** - Serial correlation or stale prices understate volatility and inflate Sharpe. Monte-Neo: smoothing (existing, returns path).

## How to measure

Metrics: Skew, kurtosis, CVaR 1%/5%, worst day/month, Sharpe adjusted for skew (e.g. Sortino, Omega), time to recover, stress replays (Feb 2018 XIV, Mar 2020).
Benchmark: Equity index; put-write index; cash.
Horizon: Must include a vol-spike event; otherwise the sample is uninformative.

## What Monte-Neo cannot verify

- Gap and liquidity events not in the sample; early assignment details with daily data
