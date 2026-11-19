# Three-fund portfolio

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `three_fund`
- **type:** [60/40 and static multi-asset allocation](../TYPES.md#balanced_60_40)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Bogleheads community (Bogle idea)
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Total US stock, total international stock, total bond; annual rebalance

Parameters (do not tune):

- `w` = 40/20/40
- `rebalance` = annual

**Data needed:** 3 TR series

**Expected regime behaviour:** diversified long-only

## Known traps

- **Rebalancing convention** - Result depends on rebalance frequency, thresholds and whether drift or costs are modelled. Monte-Neo: PLAN:rebalance_sensitivity.
- **Vendor / index construction effects** - Result depends on a proprietary index methodology or vendor-specific adjustment. Monte-Neo: not verifiable.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: CAGR, Sharpe, max drawdown, stock-bond correlation, rebalancing bonus, risk contribution by asset.
Benchmark: The same weights without rebalancing; 100% equity; cash.
Horizon: 20+ years; stock-bond correlation changes sign across eras.

## What Monte-Neo cannot verify

- Correlation regime in the future; tax drag; bond index substitution (ETF vs index)
