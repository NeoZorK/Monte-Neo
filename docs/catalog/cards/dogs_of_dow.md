# Dogs of the Dow

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `dogs_of_dow`
- **type:** [Factor / smart-beta (value, momentum, quality, low-vol, size)](../TYPES.md#factor_premia)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** O'Higgins and Downes 1991
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Buy the 10 highest-yielding Dow stocks each year

Parameters (do not tune):

- `n` = 10
- `rebalance` = annual

**Data needed:** Dow constituents, dividends

**Expected regime behaviour:** retail-popular value; 10 names

## Known traps

- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Small sample / few independent bets** - Too few trades or independent observations for a significance claim. Monte-Neo: trade-count gate, dsr (existing).
- **Post-publication decay** - Anomaly weakened after academic publication or crowding. Monte-Neo: PLAN:pre_post_publication_split.
- **Point-in-time fundamentals** - Fundamentals used with their period-end date instead of their publication date, or restated. Monte-Neo: PLAN:pit_contract (data validator).

## How to measure

Metrics: Factor alpha vs market and other factors, t-stat with multiple-testing haircut, turnover, capacity, drawdowns.
Benchmark: Cap-weighted market; Fama-French / AQR factor regressions.
Horizon: Decades; factor premia are multi-year bets.

## What Monte-Neo cannot verify

- Whether the premium persists; proprietary factor definitions
