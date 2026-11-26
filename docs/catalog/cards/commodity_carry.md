# Commodity term-structure carry

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `commodity_carry`
- **type:** [Carry (FX, commodity roll, bond roll-down, crypto funding/basis)](../TYPES.md#carry)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Gorton Rouwenhorst 2006; Erb Harvey 2006
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long backwardated, short contango commodities; monthly

Parameters (do not tune):

- `n` = top/bottom third

**Data needed:** futures curves

**Expected regime behaviour:** term structure

## Known traps

- **Futures roll yield** - Continuous contract built by naive stitching hides roll cost or gain. Monte-Neo: PLAN:roll_audit.
- **Vendor / index construction effects** - Result depends on a proprietary index methodology or vendor-specific adjustment. Monte-Neo: not verifiable.
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Funding rate and basis risk** - Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series. Monte-Neo: PLAN:carry_decomposition.

## How to measure

Metrics: Carry return vs spot return decomposition, Sharpe, skew, crash drawdowns, funding sign flips, margin usage.
Benchmark: Spot/buy-and-hold; cash.
Horizon: Includes a crisis (2008 FX, 2020 and 2022 crypto).

## What Monte-Neo cannot verify

- Counterparty/exchange default; margin calls from intraday spikes

## Worst scenario (hedged is not risk-free)

- the carry flips sign (funding, curve or rate) when it is most crowded
- the hedge leg's margin is called in a fast move
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
