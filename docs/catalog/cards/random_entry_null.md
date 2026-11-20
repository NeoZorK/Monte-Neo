# Random entry null

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `random_entry_null`
- **type:** [Negative controls and null strategies](../TYPES.md#controls)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Null model (Aronson 2006)
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Random entries with the same average holding time and exposure as a reference strategy

Parameters (do not tune):

- `seed` = 42

**Data needed:** daily OHLC

**Expected regime behaviour:** calibration

## Known traps

- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.
- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.

## How to measure

Metrics: Verdict distribution, false-positive rate of the verifier.
Benchmark: Verifier expectation (should not PASS).
Horizon: Same as the catalog.

## What Monte-Neo cannot verify

- Nothing special; they exist to measure verifier calibration
