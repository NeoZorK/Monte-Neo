# Ornstein-Uhlenbeck pairs

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `ou_pairs`
- **type:** [Statistical arbitrage and pairs trading](../TYPES.md#stat_arb_pairs)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Elliott van der Hoek Malcolm 2005
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Fit OU to spread, trade at +/- 1.5 sigma of the stationary distribution

Parameters (do not tune):

- `band_sigma` = 1.5

**Data needed:** two price series

**Expected regime behaviour:** mean-reverting spreads

## Known traps

- **Cointegration breakdown** - Spread stops mean-reverting; the relation was selected in-sample. Monte-Neo: PLAN:cointegration_suite (ADF, KPSS, Johansen, half-life, break test).
- **Parameter overfitting** - Parameters tuned on the same sample used to report performance. Monte-Neo: pbo, holdout (existing).
- **Pair / universe selection bias** - Pairs chosen by looking at the full sample are guaranteed to look cointegrated. Monte-Neo: PLAN:pair_selection_bias.

## How to measure

Metrics: Net Sharpe, spread half-life, stationarity tests out of sample, leg-level P&L, borrow cost, turnover.
Benchmark: Market-neutral zero; randomly paired null; per-leg buy-and-hold.
Horizon: Includes regime breaks; formation and trading windows separated.

## What Monte-Neo cannot verify

- Fundamental reason a spread should hold; legging risk without intraday data
