# Index (ETF vs constituents) arbitrage

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `index_arb`
- **type:** [Statistical arbitrage and pairs trading](../TYPES.md#stat_arb_pairs)
- **data tier:** C (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** ETF creation-redemption mechanism; Ben-David Franzoni Moussawi 2018 JF
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Trade the ETF against its basket when the gap to the intraday NAV exceeds the creation cost

Parameters (do not tune):

- `threshold` = creation cost + 5 bps

**Data needed:** synchronous ETF and constituent quotes, creation basket

**Expected regime behaviour:** available to authorized participants; thin for others

## Known traps

- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).
- **Capacity / liquidity** - Strategy cannot be traded at size without moving the price. Monte-Neo: PLAN:capacity_estimate (volume participation).
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Pair / universe selection bias** - Pairs chosen by looking at the full sample are guaranteed to look cointegrated. Monte-Neo: PLAN:pair_selection_bias.
- **Cointegration breakdown** - Spread stops mean-reverting; the relation was selected in-sample. Monte-Neo: PLAN:cointegration_suite (ADF, KPSS, Johansen, half-life, break test).

## How to measure

Metrics: Net Sharpe, spread half-life, stationarity tests out of sample, leg-level P&L, borrow cost, turnover.
Benchmark: Market-neutral zero; randomly paired null; per-leg buy-and-hold.
Horizon: Includes regime breaks; formation and trading windows separated.

## What Monte-Neo cannot verify

- Fundamental reason a spread should hold; legging risk without intraday data

## Worst scenario (hedged is not risk-free)

- the relationship breaks and the spread never returns
- both legs gap together in a crash while the hedge ratio is stale
- short borrow is recalled or its rate jumps
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
