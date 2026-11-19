# Value (book-to-market) HML

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `hml_value`
- **type:** [Factor / smart-beta (value, momentum, quality, low-vol, size)](../TYPES.md#factor_premia)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Fama French 1993 JFE
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Sort on book-to-market, long high third, short low third; annual June rebalance

Parameters (do not tune):

- `breakpoints` = 30/70
- `rebalance` = June annual

**Data needed:** PIT fundamentals, prices

**Expected regime behaviour:** decade-long underperformance 2007-2020

## Known traps

- **Point-in-time fundamentals** - Fundamentals used with their period-end date instead of their publication date, or restated. Monte-Neo: PLAN:pit_contract (data validator).
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Post-publication decay** - Anomaly weakened after academic publication or crowding. Monte-Neo: PLAN:pre_post_publication_split.

## How to measure

Metrics: Factor alpha vs market and other factors, t-stat with multiple-testing haircut, turnover, capacity, drawdowns.
Benchmark: Cap-weighted market; Fama-French / AQR factor regressions.
Horizon: Decades; factor premia are multi-year bets.

## What Monte-Neo cannot verify

- Whether the premium persists; proprietary factor definitions
