# Halloween (sell in May)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `halloween`
- **type:** [Calendar and seasonal effects](../TYPES.md#calendar_anomaly)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Bouman Jacobsen 2002 AER
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Hold equities Nov through Apr, cash May through Oct

Parameters (do not tune):

- `in_market` = Nov-Apr

**Data needed:** daily close

**Expected regime behaviour:** calendar

## Known traps

- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).
- **Post-publication decay** - Anomaly weakened after academic publication or crowding. Monte-Neo: PLAN:pre_post_publication_split.

## How to measure

Metrics: Mean excess return in window, t-stat with multiple-testing correction, out-of-sample persistence, net of costs.
Benchmark: Unconditional average return of the same asset.
Horizon: Decades; effects are small and fragile.

## What Monte-Neo cannot verify

- Causal reasons; stability in the future
