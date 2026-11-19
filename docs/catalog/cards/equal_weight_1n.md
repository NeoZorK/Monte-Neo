# Equal weight 1/N

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `equal_weight_1n`
- **type:** [Equal weight (1/N) and naive diversification](../TYPES.md#equal_weight)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** DeMiguel Garlappi Uppal 2009
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Equal weight of the universe, monthly rebalance

Parameters (do not tune):

- `rebalance` = monthly

**Data needed:** point-in-time universe

**Expected regime behaviour:** small-cap tilt; needs PIT universe

## Known traps

- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Capacity / liquidity** - Strategy cannot be traded at size without moving the price. Monte-Neo: PLAN:capacity_estimate (volume participation).
- **Rebalancing convention** - Result depends on rebalance frequency, thresholds and whether drift or costs are modelled. Monte-Neo: PLAN:rebalance_sensitivity.

## How to measure

Metrics: Sharpe, turnover, concentration vs cap-weight, small-cap tilt.
Benchmark: Cap-weighted index of the same universe.
Horizon: 10+ years.

## What Monte-Neo cannot verify

- Illiquidity of small constituents at scale
