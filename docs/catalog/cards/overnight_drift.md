# Overnight drift

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `overnight_drift`
- **type:** [Calendar and seasonal effects](../TYPES.md#calendar_anomaly)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Cooper Cliff Gulen 2008; Berkman et al. 2012
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Buy at close, sell at next open

Parameters (do not tune):

- none

**Data needed:** daily open and close

**Expected regime behaviour:** needs very low costs; daily bars hide execution

## Known traps

- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Execution timing** - Trade assumed at the close/open that generated the signal. Monte-Neo: lookahead, timing (existing).
- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.
- **Post-publication decay** - Anomaly weakened after academic publication or crowding. Monte-Neo: PLAN:pre_post_publication_split.

## How to measure

Metrics: Mean excess return in window, t-stat with multiple-testing correction, out-of-sample persistence, net of costs.
Benchmark: Unconditional average return of the same asset.
Horizon: Decades; effects are small and fragile.

## What Monte-Neo cannot verify

- Causal reasons; stability in the future
