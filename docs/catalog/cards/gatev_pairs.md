# Distance pairs trading

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `gatev_pairs`
- **type:** [Statistical arbitrage and pairs trading](../TYPES.md#stat_arb_pairs)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Gatev Goetzmann Rouwenhorst 2006 RFS
- **verification (2026-11-08):** confirmed-secondary: 12m formation, 6m trading, 20 min-distance pairs, open at 2 std, close on crossing (summaries, 2026-11-08); primary text not read

## Definition (frozen, from the source)

Normalize prices over 12-month formation, pick 20 pairs with min SSD, trade 6 months; open at 2 std divergence, close at crossing

Parameters (do not tune):

- `formation_months` = 12
- `trade_months` = 6
- `pairs` = 20
- `open_std` = 2.0

**Data needed:** PIT equity or coin panel

**Expected regime behaviour:** decaying profitability

## Known traps

- **Pair / universe selection bias** - Pairs chosen by looking at the full sample are guaranteed to look cointegrated. Monte-Neo: PLAN:pair_selection_bias.
- **Cointegration breakdown** - Spread stops mean-reverting; the relation was selected in-sample. Monte-Neo: PLAN:cointegration_suite (ADF, KPSS, Johansen, half-life, break test).
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Short-sale cost and availability** - Borrow fees, locates and recalls are ignored for the short leg. Monte-Neo: PLAN:borrow_model.

## How to measure

Metrics: Net Sharpe, spread half-life, stationarity tests out of sample, leg-level P&L, borrow cost, turnover.
Benchmark: Market-neutral zero; randomly paired null; per-leg buy-and-hold.
Horizon: Includes regime breaks; formation and trading windows separated.

## What Monte-Neo cannot verify

- Fundamental reason a spread should hold; legging risk without intraday data
