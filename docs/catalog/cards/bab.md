# Betting against beta

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `bab`
- **type:** [Factor / smart-beta (value, momentum, quality, low-vol, size)](../TYPES.md#factor_premia)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Frazzini Pedersen 2014 JFE
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long low-beta levered to beta 1, short high-beta de-levered to beta 1

Parameters (do not tune):

- `beta_window` = 1y vol, 5y corr
- `shrink` = 0.6

**Data needed:** PIT equity universe, financing rate

**Expected regime behaviour:** needs leverage and funding

## Known traps

- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.
- **Short-sale cost and availability** - Borrow fees, locates and recalls are ignored for the short leg. Monte-Neo: PLAN:borrow_model.
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Point-in-time fundamentals** - Fundamentals used with their period-end date instead of their publication date, or restated. Monte-Neo: PLAN:pit_contract (data validator).
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).

## How to measure

Metrics: Factor alpha vs market and other factors, t-stat with multiple-testing haircut, turnover, capacity, drawdowns.
Benchmark: Cap-weighted market; Fama-French / AQR factor regressions.
Horizon: Decades; factor premia are multi-year bets.

## What Monte-Neo cannot verify

- Whether the premium persists; proprietary factor definitions
