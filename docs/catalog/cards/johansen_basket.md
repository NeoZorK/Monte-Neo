# Johansen basket mean reversion

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `johansen_basket`
- **type:** [Statistical arbitrage and pairs trading](../TYPES.md#stat_arb_pairs)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Johansen 1991; Chan 2013
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Johansen eigenvector as basket weights; trade z-score of basket value

Parameters (do not tune):

- `entry_z` = 1.0
- `lookback_days` = 120

**Data needed:** 3+ related price series

**Expected regime behaviour:** needs cointegrated basket

## Known traps

- **Pair / universe selection bias** - Pairs chosen by looking at the full sample are guaranteed to look cointegrated. Monte-Neo: PLAN:pair_selection_bias.
- **Cointegration breakdown** - Spread stops mean-reverting; the relation was selected in-sample. Monte-Neo: PLAN:cointegration_suite (ADF, KPSS, Johansen, half-life, break test).

## How to measure

Metrics: Net Sharpe, spread half-life, stationarity tests out of sample, leg-level P&L, borrow cost, turnover.
Benchmark: Market-neutral zero; randomly paired null; per-leg buy-and-hold.
Horizon: Includes regime breaks; formation and trading windows separated.

## What Monte-Neo cannot verify

- Fundamental reason a spread should hold; legging risk without intraday data
