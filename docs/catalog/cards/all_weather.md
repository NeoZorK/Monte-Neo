# All Weather style (static approximation)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `all_weather`
- **type:** [Risk parity / inverse-volatility / equal risk contribution](../TYPES.md#risk_parity)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Bridgewater public description (Dalio); approximations by third parties
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

30% stocks, 40% long Treasuries, 15% intermediate Treasuries, 7.5% gold, 7.5% commodities

Parameters (do not tune):

- `w` = 30/40/15/7.5/7.5
- `rebalance` = annual

**Data needed:** 5 TR series

**Expected regime behaviour:** static proxy, not the actual fund

## Known traps

- **Rebalancing convention** - Result depends on rebalance frequency, thresholds and whether drift or costs are modelled. Monte-Neo: PLAN:rebalance_sensitivity.
- **Vendor / index construction effects** - Result depends on a proprietary index methodology or vendor-specific adjustment. Monte-Neo: not verifiable.
- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).

## How to measure

Metrics: Sharpe, vol-targeting realized vs target, max drawdown, leverage used, financing cost.
Benchmark: 60/40 and equal weight at matched volatility.
Horizon: Includes a rising-rate era and a stock-bond correlation flip.

## What Monte-Neo cannot verify

- Cost of leverage obtainable by the user; futures vs ETF implementation differences
