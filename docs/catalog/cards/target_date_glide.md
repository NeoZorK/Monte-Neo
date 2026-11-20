# Target-date glide path

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `target_date_glide`
- **type:** [Rebalancing and glide-path policies (constant-mix, CPPI, target-date)](../TYPES.md#rebalancing_policy)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Industry glide paths (e.g. Vanguard public descriptions)
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Equity share falls linearly from 90% at 40 years to retirement to 50% at retirement

Parameters (do not tune):

- `start_equity` = 0.9
- `end_equity` = 0.5
- `horizon_years` = 40

**Data needed:** equity and bond series

**Expected regime behaviour:** lifetime policy; needs simulation

## Known traps

- **Rebalancing convention** - Result depends on rebalance frequency, thresholds and whether drift or costs are modelled. Monte-Neo: PLAN:rebalance_sensitivity.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Terminal wealth distribution, shortfall probability, path dependence, turnover, cost drag.
Benchmark: Buy-and-hold with the same initial weights.
Horizon: Investor lifetime; needs simulated and historical paths.

## What Monte-Neo cannot verify

- Investor behaviour; the tax and lifetime-income context
