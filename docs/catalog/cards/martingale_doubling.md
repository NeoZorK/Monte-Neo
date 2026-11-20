# Martingale doubling (negative control)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `martingale_doubling`
- **type:** [Negative controls and null strategies](../TYPES.md#controls)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Gambling folklore; no investment source
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Double position size after each loss

Parameters (do not tune):

- `multiplier` = 2

**Data needed:** daily OHLC

**Expected regime behaviour:** expected to be rejected

## Known traps

- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.

## How to measure

Metrics: Verdict distribution, false-positive rate of the verifier.
Benchmark: Verifier expectation (should not PASS).
Horizon: Same as the catalog.

## What Monte-Neo cannot verify

- Nothing special; they exist to measure verifier calibration
