# PCA residual stat-arb

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `avellaneda_lee_pca`
- **type:** [Statistical arbitrage and pairs trading](../TYPES.md#stat_arb_pairs)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Avellaneda Lee 2010
- **verification (2026-11-08):** partial: open at s=1.25 confirmed in a secondary write-up; close levels corrected to 0.75 short / -0.50 long; window and factor count unverified

## Definition (frozen, from the source)

Regress returns on top PCA factors (60-day window); trade s-score of OU residuals: open at 1.25; close short at 0.75, close long at -0.50

Parameters (do not tune):

- `open_s` = 1.25
- `close_short_s` = 0.75
- `close_long_s` = -0.5
- `window` = unverified (60 days in our draft)
- `factors` = unverified (15 in our draft)

**Data needed:** PIT equity panel

**Expected regime behaviour:** collapsed post-2008 in public evidence

## Known traps

- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Capacity / liquidity** - Strategy cannot be traded at size without moving the price. Monte-Neo: PLAN:capacity_estimate (volume participation).
- **Short-sale cost and availability** - Borrow fees, locates and recalls are ignored for the short leg. Monte-Neo: PLAN:borrow_model.
- **Pair / universe selection bias** - Pairs chosen by looking at the full sample are guaranteed to look cointegrated. Monte-Neo: PLAN:pair_selection_bias.
- **Cointegration breakdown** - Spread stops mean-reverting; the relation was selected in-sample. Monte-Neo: PLAN:cointegration_suite (ADF, KPSS, Johansen, half-life, break test).

## How to measure

Metrics: Net Sharpe, spread half-life, stationarity tests out of sample, leg-level P&L, borrow cost, turnover.
Benchmark: Market-neutral zero; randomly paired null; per-leg buy-and-hold.
Horizon: Includes regime breaks; formation and trading windows separated.

## What Monte-Neo cannot verify

- Fundamental reason a spread should hold; legging risk without intraday data
