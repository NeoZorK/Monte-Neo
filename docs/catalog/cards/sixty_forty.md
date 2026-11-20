# 60/40 stocks/bonds

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `sixty_forty`
- **type:** [60/40 and static multi-asset allocation](../TYPES.md#balanced_60_40)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Industry standard; Perold-Sharpe 1988
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

60% equity index, 40% aggregate bond, rebalance monthly

Parameters (do not tune):

- `w_equity` = 0.6
- `w_bond` = 0.4
- `rebalance` = monthly

**Data needed:** equity TR, bond TR

**Expected regime behaviour:** works when stock-bond correlation is low or negative

## Known traps

- **Rebalancing convention** - Result depends on rebalance frequency, thresholds and whether drift or costs are modelled. Monte-Neo: PLAN:rebalance_sensitivity.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: CAGR, Sharpe, max drawdown, stock-bond correlation, rebalancing bonus, risk contribution by asset.
Benchmark: The same weights without rebalancing; 100% equity; cash.
Horizon: 20+ years; stock-bond correlation changes sign across eras.

## What Monte-Neo cannot verify

- Correlation regime in the future; tax drag; bond index substitution (ETF vs index)
