# Turn-of-the-month

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `turn_of_month`
- **type:** [Calendar and seasonal effects](../TYPES.md#calendar_anomaly)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Ariel 1987; Lakonishok Smidt 1988
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Hold from the last trading day of the month through the 3rd trading day of the next

Parameters (do not tune):

- `days` = -1 to +3

**Data needed:** daily close

**Expected regime behaviour:** calendar

## Known traps

- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.
- **Post-publication decay** - Anomaly weakened after academic publication or crowding. Monte-Neo: PLAN:pre_post_publication_split.

## How to measure

Metrics: Mean excess return in window, t-stat with multiple-testing correction, out-of-sample persistence, net of costs.
Benchmark: Unconditional average return of the same asset.
Horizon: Decades; effects are small and fragile.

## What Monte-Neo cannot verify

- Causal reasons; stability in the future
