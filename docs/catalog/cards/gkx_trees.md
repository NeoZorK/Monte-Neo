# Gradient-boosted cross-sectional forecast

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `gkx_trees`
- **type:** [Machine-learning forecast](../TYPES.md#ml_forecast)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Gu Kelly Xiu 2020 RFS
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Boosted trees on 94 firm characteristics plus 8 macro variables predict next-month returns; long top decile, short bottom; annual refit with a validation year

Parameters (do not tune):

- `model` = gradient boosted trees
- `refit` = annual
- `deciles` = 10

**Data needed:** point-in-time characteristics, monthly returns

**Expected regime behaviour:** the paper reports strongest gains in small, illiquid stocks

## Known traps

- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Parameter overfitting** - Parameters tuned on the same sample used to report performance. Monte-Neo: pbo, holdout (existing).
- **Point-in-time fundamentals** - Fundamentals used with their period-end date instead of their publication date, or restated. Monte-Neo: PLAN:pit_contract (data validator).
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).

## How to measure

Metrics: Out-of-sample IC and its t-stat, net Sharpe, refit gap (train vs test), feature leakage audit, turnover.
Benchmark: The same portfolio rule on a linear model with few features; zero.
Horizon: Walk-forward with purged and embargoed folds.

## What Monte-Neo cannot verify

- What the model learned; whether a foundation model saw the test period

## Worst scenario (hedged is not risk-free)

- **This strategy:** the long and short deciles reverse together in a factor crash; the model learns the regime it was trained on
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
