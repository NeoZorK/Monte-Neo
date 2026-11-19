# Short-vol ETP buy and hold

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `svxy_short_vol_etp`
- **type:** [Volatility selling / short vol](../TYPES.md#short_volatility)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Product methodology; Feb 2018 event
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Hold an inverse VIX short-term futures ETP

Parameters (do not tune):

- `leverage` = -0.5x or -1x

**Data needed:** ETP price history incl. termination

**Expected regime behaviour:** XIV terminated 2018-02-21

## Known traps

- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Return smoothing / stale marks** - Serial correlation or stale prices understate volatility and inflate Sharpe. Monte-Neo: smoothing (existing, returns path).

## How to measure

Metrics: Skew, kurtosis, CVaR 1%/5%, worst day/month, Sharpe adjusted for skew (e.g. Sortino, Omega), time to recover, stress replays (Feb 2018 XIV, Mar 2020).
Benchmark: Equity index; put-write index; cash.
Horizon: Must include a vol-spike event; otherwise the sample is uninformative.

## What Monte-Neo cannot verify

- Gap and liquidity events not in the sample; early assignment details with daily data
