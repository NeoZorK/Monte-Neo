# Hierarchical risk parity

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `hrp`
- **type:** [Minimum variance / max diversification / HRP](../TYPES.md#minimum_variance)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Lopez de Prado 2016 JPM
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Cluster by correlation distance, quasi-diagonalize, recursive bisection by inverse variance; monthly

Parameters (do not tune):

- `linkage` = single
- `cov_window` = 252
- `rebalance` = monthly

**Data needed:** multi-asset returns

**Expected regime behaviour:** diversified

## Known traps

- **Parameter overfitting** - Parameters tuned on the same sample used to report performance. Monte-Neo: pbo, holdout (existing).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.

## How to measure

Metrics: Realized volatility vs equal weight, Sharpe, turnover, estimation window sensitivity.
Benchmark: Equal weight and cap-weight of the same universe.
Horizon: 10+ years, out of sample with expanding covariance window.

## What Monte-Neo cannot verify

- Covariance stability in the future
