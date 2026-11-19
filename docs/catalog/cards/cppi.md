# Constant proportion portfolio insurance

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `cppi`
- **type:** [Rebalancing and glide-path policies (constant-mix, CPPI, target-date)](../TYPES.md#rebalancing_policy)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Black Jones 1987
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Risky exposure = m * (wealth - floor)

Parameters (do not tune):

- `multiplier` = 4
- `floor` = 0.8
- `rebalance` = daily

**Data needed:** risky and safe series

**Expected regime behaviour:** gap risk breaks the floor

## Known traps

- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Execution timing** - Trade assumed at the close/open that generated the signal. Monte-Neo: lookahead, timing (existing).
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Rebalancing convention** - Result depends on rebalance frequency, thresholds and whether drift or costs are modelled. Monte-Neo: PLAN:rebalance_sensitivity.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Terminal wealth distribution, shortfall probability, path dependence, turnover, cost drag.
Benchmark: Buy-and-hold with the same initial weights.
Horizon: Investor lifetime; needs simulated and historical paths.

## What Monte-Neo cannot verify

- Investor behaviour; the tax and lifetime-income context
