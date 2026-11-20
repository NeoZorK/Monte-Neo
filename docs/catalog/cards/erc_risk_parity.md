# Equal risk contribution

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `erc_risk_parity`
- **type:** [Risk parity / inverse-volatility / equal risk contribution](../TYPES.md#risk_parity)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Maillard Roncalli Teiletche 2010
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Solve weights so each asset contributes equal risk; full covariance, 252-day window; monthly

Parameters (do not tune):

- `cov_window` = 252
- `rebalance` = monthly

**Data needed:** multi-asset returns

**Expected regime behaviour:** bond-heavy; leverage optional (default none)

## Known traps

- **Parameter overfitting** - Parameters tuned on the same sample used to report performance. Monte-Neo: pbo, holdout (existing).
- **Rebalancing convention** - Result depends on rebalance frequency, thresholds and whether drift or costs are modelled. Monte-Neo: PLAN:rebalance_sensitivity.
- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).

## How to measure

Metrics: Sharpe, vol-targeting realized vs target, max drawdown, leverage used, financing cost.
Benchmark: 60/40 and equal weight at matched volatility.
Horizon: Includes a rising-rate era and a stock-bond correlation flip.

## What Monte-Neo cannot verify

- Cost of leverage obtainable by the user; futures vs ETF implementation differences
