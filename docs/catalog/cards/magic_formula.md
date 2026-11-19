# Magic formula

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `magic_formula`
- **type:** [Factor / smart-beta (value, momentum, quality, low-vol, size)](../TYPES.md#factor_premia)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Greenblatt 2005 The Little Book That Beats the Market
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Rank by earnings yield and return on capital; buy top 30, hold 1 year

Parameters (do not tune):

- `n` = 30
- `hold_months` = 12

**Data needed:** PIT fundamentals

**Expected regime behaviour:** retail-popular value/quality

## Known traps

- **Point-in-time fundamentals** - Fundamentals used with their period-end date instead of their publication date, or restated. Monte-Neo: PLAN:pit_contract (data validator).
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.

## How to measure

Metrics: Factor alpha vs market and other factors, t-stat with multiple-testing haircut, turnover, capacity, drawdowns.
Benchmark: Cap-weighted market; Fama-French / AQR factor regressions.
Horizon: Decades; factor premia are multi-year bets.

## What Monte-Neo cannot verify

- Whether the premium persists; proprietary factor definitions
