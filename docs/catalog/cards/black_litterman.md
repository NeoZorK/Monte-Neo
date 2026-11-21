# Black-Litterman with momentum views

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `black_litterman`
- **type:** [Minimum variance / max diversification / HRP](../TYPES.md#minimum_variance)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Black Litterman 1992 FAJ; He Litterman 1999
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Equilibrium returns from market weights; one view per asset = sign of 12-month return with confidence from its t-stat; long-only optimum; monthly

Parameters (do not tune):

- `tau` = 0.05
- `risk_aversion` = 2.5
- `rebalance` = monthly

**Data needed:** multi-asset returns, market weights

**Expected regime behaviour:** stays near market weights unless views are strong

## Known traps

- **Parameter overfitting** - Parameters tuned on the same sample used to report performance. Monte-Neo: pbo, holdout (existing).
- **Rebalancing convention** - Result depends on rebalance frequency, thresholds and whether drift or costs are modelled. Monte-Neo: PLAN:rebalance_sensitivity.
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.

## How to measure

Metrics: Realized volatility vs equal weight, Sharpe, turnover, estimation window sensitivity.
Benchmark: Equal weight and cap-weight of the same universe.
Horizon: 10+ years, out of sample with expanding covariance window.

## What Monte-Neo cannot verify

- Covariance stability in the future
