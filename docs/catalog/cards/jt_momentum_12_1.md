# Cross-sectional momentum 12-1

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `jt_momentum_12_1`
- **type:** [Cross-sectional momentum and reversal](../TYPES.md#xs_momentum)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Jegadeesh Titman 1993 JF
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Rank by return months t-12 to t-2 (skip 1); long top decile, short bottom; hold 1 month (or 6)

Parameters (do not tune):

- `formation` = 12
- `skip` = 1
- `hold` = 1
- `deciles` = 10

**Data needed:** PIT equity universe with delistings

**Expected regime behaviour:** momentum crashes in rebounds

## Known traps

- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Crash / momentum-crash risk** - Large drawdown clustered in market rebounds or crises. Monte-Neo: PLAN:tail_skew_profile.
- **Short-sale cost and availability** - Borrow fees, locates and recalls are ignored for the short leg. Monte-Neo: PLAN:borrow_model.

## How to measure

Metrics: Long-short Sharpe, alpha vs factors, momentum-crash drawdowns, turnover, net-of-cost return.
Benchmark: Market and Fama-French plus UMD.
Horizon: Decades; reversal is a short-horizon, high-turnover effect.

## What Monte-Neo cannot verify

- Crash timing; short availability
