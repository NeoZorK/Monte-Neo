# Residual momentum

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `residual_momentum`
- **type:** [Cross-sectional momentum and reversal](../TYPES.md#xs_momentum)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Blitz Huij Martens 2011 J. Empirical Finance
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Momentum on residuals from FF3 regression, 36-month estimation

Parameters (do not tune):

- `estimation` = 36
- `formation` = 12
- `skip` = 1

**Data needed:** PIT equity universe, FF3 factors

**Expected regime behaviour:** lower factor exposure

## Known traps

- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Crash / momentum-crash risk** - Large drawdown clustered in market rebounds or crises. Monte-Neo: PLAN:tail_skew_profile.

## How to measure

Metrics: Long-short Sharpe, alpha vs factors, momentum-crash drawdowns, turnover, net-of-cost return.
Benchmark: Market and Fama-French plus UMD.
Horizon: Decades; reversal is a short-horizon, high-turnover effect.

## What Monte-Neo cannot verify

- Crash timing; short availability
