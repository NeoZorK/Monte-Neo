# Pre-FOMC announcement drift

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `fomc_drift`
- **type:** [Calendar and seasonal effects](../TYPES.md#calendar_anomaly)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Lucca Moench 2015 JF
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Hold equities from close before to 2:15pm on FOMC announcement day

Parameters (do not tune):

- `window` = 24h before announcement

**Data needed:** intraday, FOMC dates

**Expected regime behaviour:** intraday

## Known traps

- **Post-publication decay** - Anomaly weakened after academic publication or crowding. Monte-Neo: PLAN:pre_post_publication_split.
- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).
- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.

## How to measure

Metrics: Mean excess return in window, t-stat with multiple-testing correction, out-of-sample persistence, net of costs.
Benchmark: Unconditional average return of the same asset.
Horizon: Decades; effects are small and fragile.

## What Monte-Neo cannot verify

- Causal reasons; stability in the future
