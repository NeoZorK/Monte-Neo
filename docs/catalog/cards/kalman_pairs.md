# Kalman hedge-ratio pairs

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `kalman_pairs`
- **type:** [Statistical arbitrage and pairs trading](../TYPES.md#stat_arb_pairs)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Chan 2013 Algorithmic Trading
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Kalman filter estimates time-varying hedge ratio; trade z-score of prediction error

Parameters (do not tune):

- `entry_z` = 1.0
- `exit_z` = 0.0
- `delta` = 0.0001

**Data needed:** two price series

**Expected regime behaviour:** slow-changing relation

## Known traps

- **Parameter overfitting** - Parameters tuned on the same sample used to report performance. Monte-Neo: pbo, holdout (existing).
- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Pair / universe selection bias** - Pairs chosen by looking at the full sample are guaranteed to look cointegrated. Monte-Neo: PLAN:pair_selection_bias.
- **Cointegration breakdown** - Spread stops mean-reverting; the relation was selected in-sample. Monte-Neo: PLAN:cointegration_suite (ADF, KPSS, Johansen, half-life, break test).

## How to measure

Metrics: Net Sharpe, spread half-life, stationarity tests out of sample, leg-level P&L, borrow cost, turnover.
Benchmark: Market-neutral zero; randomly paired null; per-leg buy-and-hold.
Horizon: Includes regime breaks; formation and trading windows separated.

## What Monte-Neo cannot verify

- Fundamental reason a spread should hold; legging risk without intraday data

## Worst scenario (hedged is not risk-free)

- the relationship breaks and the spread never returns
- both legs gap together in a crash while the hedge ratio is stale
- short borrow is recalled or its rate jumps
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
