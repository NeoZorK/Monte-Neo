# Industry momentum

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `industry_momentum`
- **type:** [Cross-sectional momentum and reversal](../TYPES.md#xs_momentum)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Moskowitz Grinblatt 1999 JF
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long past-winning industries, short losing; 6-month formation

Parameters (do not tune):

- `formation` = 6
- `hold` = 1

**Data needed:** industry index returns

**Expected regime behaviour:** industry-level

## Known traps

- **Crash / momentum-crash risk** - Large drawdown clustered in market rebounds or crises. Monte-Neo: PLAN:tail_skew_profile.
- **Short-sale cost and availability** - Borrow fees, locates and recalls are ignored for the short leg. Monte-Neo: PLAN:borrow_model.
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).

## How to measure

Metrics: Long-short Sharpe, alpha vs factors, momentum-crash drawdowns, turnover, net-of-cost return.
Benchmark: Market and Fama-French plus UMD.
Horizon: Decades; reversal is a short-horizon, high-turnover effect.

## What Monte-Neo cannot verify

- Crash timing; short availability
