# 52-week high momentum

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `fifty_two_week_high`
- **type:** [Cross-sectional momentum and reversal](../TYPES.md#xs_momentum)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** George Hwang 2004 JF
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Rank by price / 52-week high; long top, short bottom

Parameters (do not tune):

- `window` = 252
- `hold` = 6

**Data needed:** PIT equity universe

**Expected regime behaviour:** anchoring effect

## Known traps

- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Crash / momentum-crash risk** - Large drawdown clustered in market rebounds or crises. Monte-Neo: PLAN:tail_skew_profile.

## How to measure

Metrics: Long-short Sharpe, alpha vs factors, momentum-crash drawdowns, turnover, net-of-cost return.
Benchmark: Market and Fama-French plus UMD.
Horizon: Decades; reversal is a short-horizon, high-turnover effect.

## What Monte-Neo cannot verify

- Crash timing; short availability
