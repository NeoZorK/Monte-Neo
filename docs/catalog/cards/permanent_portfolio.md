# Permanent Portfolio

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `permanent_portfolio`
- **type:** [60/40 and static multi-asset allocation](../TYPES.md#balanced_60_40)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Browne 1987 Fail-Safe Investing
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

25% stocks, 25% long bonds, 25% gold, 25% cash; rebalance annually or by 15% bands

Parameters (do not tune):

- `w` = 25/25/25/25
- `rebalance` = annual

**Data needed:** stock, long bond, gold, cash

**Expected regime behaviour:** designed to survive four macro regimes

## Known traps

- **Rebalancing convention** - Result depends on rebalance frequency, thresholds and whether drift or costs are modelled. Monte-Neo: PLAN:rebalance_sensitivity.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: CAGR, Sharpe, max drawdown, stock-bond correlation, rebalancing bonus, risk contribution by asset.
Benchmark: The same weights without rebalancing; 100% equity; cash.
Horizon: 20+ years; stock-bond correlation changes sign across eras.

## What Monte-Neo cannot verify

- Correlation regime in the future; tax drag; bond index substitution (ETF vs index)
