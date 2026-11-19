# Inverse volatility weighting

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `inverse_vol`
- **type:** [Risk parity / inverse-volatility / equal risk contribution](../TYPES.md#risk_parity)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Qian 2005; common naive risk parity
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

w_i proportional to 1/sigma_i; sigma from 60 trading days; monthly

Parameters (do not tune):

- `vol_window` = 60
- `rebalance` = monthly

**Data needed:** multi-asset returns

**Expected regime behaviour:** unlevered naive risk parity

## Known traps

- **Rebalancing convention** - Result depends on rebalance frequency, thresholds and whether drift or costs are modelled. Monte-Neo: PLAN:rebalance_sensitivity.
- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).

## How to measure

Metrics: Sharpe, vol-targeting realized vs target, max drawdown, leverage used, financing cost.
Benchmark: 60/40 and equal weight at matched volatility.
Horizon: Includes a rising-rate era and a stock-bond correlation flip.

## What Monte-Neo cannot verify

- Cost of leverage obtainable by the user; futures vs ETF implementation differences
