# Low volatility

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `low_vol_ang`
- **type:** [Factor / smart-beta (value, momentum, quality, low-vol, size)](../TYPES.md#factor_premia)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Ang Hodrick Xing Zhang 2006 JF; Haugen Baker 1991
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long lowest-volatility quintile (60-day idiosyncratic or total vol)

Parameters (do not tune):

- `window` = 60
- `quantile` = 5

**Data needed:** PIT equity universe

**Expected regime behaviour:** defensive; sector concentrated

## Known traps

- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Capacity / liquidity** - Strategy cannot be traded at size without moving the price. Monte-Neo: PLAN:capacity_estimate (volume participation).
- **Point-in-time fundamentals** - Fundamentals used with their period-end date instead of their publication date, or restated. Monte-Neo: PLAN:pit_contract (data validator).
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).

## How to measure

Metrics: Factor alpha vs market and other factors, t-stat with multiple-testing haircut, turnover, capacity, drawdowns.
Benchmark: Cap-weighted market; Fama-French / AQR factor regressions.
Horizon: Decades; factor premia are multi-year bets.

## What Monte-Neo cannot verify

- Whether the premium persists; proprietary factor definitions
