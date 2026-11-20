# FX momentum

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `fx_momentum`
- **type:** [Cross-sectional momentum and reversal](../TYPES.md#xs_momentum)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Menkhoff Sarno Schmeling Schrimpf 2012 JFE
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long past-12-month winning currencies, short losers; monthly

Parameters (do not tune):

- `formation` = 12
- `hold` = 1

**Data needed:** FX spot and forwards

**Expected regime behaviour:** currency

## Known traps

- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Crash / momentum-crash risk** - Large drawdown clustered in market rebounds or crises. Monte-Neo: PLAN:tail_skew_profile.
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).

## How to measure

Metrics: Long-short Sharpe, alpha vs factors, momentum-crash drawdowns, turnover, net-of-cost return.
Benchmark: Market and Fama-French plus UMD.
Horizon: Decades; reversal is a short-horizon, high-turnover effect.

## What Monte-Neo cannot verify

- Crash timing; short availability
