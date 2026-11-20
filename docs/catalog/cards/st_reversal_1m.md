# Short-term reversal 1 month

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `st_reversal_1m`
- **type:** [Cross-sectional momentum and reversal](../TYPES.md#xs_momentum)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Jegadeesh 1990 JF
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long prior-month losers, short winners; monthly

Parameters (do not tune):

- `formation` = 1
- `hold` = 1

**Data needed:** PIT equity universe

**Expected regime behaviour:** liquidity provision; heavy turnover

## Known traps

- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Capacity / liquidity** - Strategy cannot be traded at size without moving the price. Monte-Neo: PLAN:capacity_estimate (volume participation).
- **Stale prices / illiquid quotes** - Last trade used as executable price in thin markets. Monte-Neo: data_integrity (partly).
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Crash / momentum-crash risk** - Large drawdown clustered in market rebounds or crises. Monte-Neo: PLAN:tail_skew_profile.

## How to measure

Metrics: Long-short Sharpe, alpha vs factors, momentum-crash drawdowns, turnover, net-of-cost return.
Benchmark: Market and Fama-French plus UMD.
Horizon: Decades; reversal is a short-horizon, high-turnover effect.

## What Monte-Neo cannot verify

- Crash timing; short availability
