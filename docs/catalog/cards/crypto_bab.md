# Betting against beta in crypto

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `crypto_bab`
- **type:** [Factor / smart-beta (value, momentum, quality, low-vol, size)](../TYPES.md#factor_premia)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Frazzini Pedersen 2014 JFE, applied to crypto perpetuals
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Rank coins by 90-day beta to BTC; long the lowest third levered to beta 1, short the highest third de-levered to beta 1; monthly

Parameters (do not tune):

- `beta_window` = 90
- `quantiles` = 3
- `rebalance` = monthly

**Data needed:** perpetual daily closes of 15+ coins with delistings

**Expected regime behaviour:** low-beta coins lag in alt seasons

## Known traps

- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.
- **Short-sale cost and availability** - Borrow fees, locates and recalls are ignored for the short leg. Monte-Neo: PLAN:borrow_model.
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Point-in-time fundamentals** - Fundamentals used with their period-end date instead of their publication date, or restated. Monte-Neo: PLAN:pit_contract (data validator).

## How to measure

Metrics: Factor alpha vs market and other factors, t-stat with multiple-testing haircut, turnover, capacity, drawdowns.
Benchmark: Cap-weighted market; Fama-French / AQR factor regressions.
Horizon: Decades; factor premia are multi-year bets.

## What Monte-Neo cannot verify

- Whether the premium persists; proprietary factor definitions

## Worst scenario (hedged is not risk-free)

- **This strategy:** an alt season lifts high-beta coins far above their betas; levered low-beta legs lose with the market in a crash
- the long and short legs reverse together in a factor crash (momentum 2009, value 2020)
- short borrow costs or recalls
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
