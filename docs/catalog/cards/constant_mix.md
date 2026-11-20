# Constant-mix rebalancing

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `constant_mix`
- **type:** [Rebalancing and glide-path policies (constant-mix, CPPI, target-date)](../TYPES.md#rebalancing_policy)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Perold Sharpe 1988
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Keep fixed risky share; rebalance monthly to target

Parameters (do not tune):

- `risky` = 0.6
- `rebalance` = monthly

**Data needed:** risky and safe series

**Expected regime behaviour:** concave in trends, convex in mean reversion

## Known traps

- **Rebalancing convention** - Result depends on rebalance frequency, thresholds and whether drift or costs are modelled. Monte-Neo: PLAN:rebalance_sensitivity.
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Terminal wealth distribution, shortfall probability, path dependence, turnover, cost drag.
Benchmark: Buy-and-hold with the same initial weights.
Horizon: Investor lifetime; needs simulated and historical paths.

## What Monte-Neo cannot verify

- Investor behaviour; the tax and lifetime-income context
