# Monthly iron condor

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `iron_condor`
- **type:** [Volatility selling / short vol](../TYPES.md#short_volatility)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Retail practice; no academic source
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Sell 16-delta put and call wings 30 DTE, buy wings

Parameters (do not tune):

- `delta` = 0.16
- `dte` = 30

**Data needed:** option chains

**Expected regime behaviour:** range markets

## Known traps

- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).
- **Return smoothing / stale marks** - Serial correlation or stale prices understate volatility and inflate Sharpe. Monte-Neo: smoothing (existing, returns path).

## How to measure

Metrics: Skew, kurtosis, CVaR 1%/5%, worst day/month, Sharpe adjusted for skew (e.g. Sortino, Omega), time to recover, stress replays (Feb 2018 XIV, Mar 2020).
Benchmark: Equity index; put-write index; cash.
Horizon: Must include a vol-spike event; otherwise the sample is uninformative.

## What Monte-Neo cannot verify

- Gap and liquidity events not in the sample; early assignment details with daily data
