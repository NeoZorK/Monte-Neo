# Basket of crypto pairs (rolling hedge)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `crypto_pairs_basket`
- **type:** [Statistical arbitrage and pairs trading](../TYPES.md#stat_arb_pairs)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Gatev Goetzmann Rouwenhorst 2006 RFS (distance pairs) applied to a basket of related perpetuals
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Six pairs (ETH/BTC, SOL/ETH, BNB/BTC, LTC/BTC, LINK/ETH, ADA/XRP): rolling 90-day hedge ratio on log prices; sell the spread above z 2, buy below -2, close inside 0.5, stop beyond 4; equal risk per pair

Parameters (do not tune):

- `window` = 90
- `entry` = 2.0
- `exit` = 0.5
- `stop` = 4.0

**Data needed:** perpetual daily closes of 10 coins, funding history

**Expected regime behaviour:** works while relationships hold; listings and narratives break them

## Known traps

- **Cointegration breakdown** - Spread stops mean-reverting; the relation was selected in-sample. Monte-Neo: PLAN:cointegration_suite (ADF, KPSS, Johansen, half-life, break test).
- **Pair / universe selection bias** - Pairs chosen by looking at the full sample are guaranteed to look cointegrated. Monte-Neo: PLAN:pair_selection_bias.
- **Funding rate and basis risk** - Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series. Monte-Neo: PLAN:carry_decomposition.
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).

## How to measure

Metrics: Net Sharpe, spread half-life, stationarity tests out of sample, leg-level P&L, borrow cost, turnover.
Benchmark: Market-neutral zero; randomly paired null; per-leg buy-and-hold.
Horizon: Includes regime breaks; formation and trading windows separated.

## What Monte-Neo cannot verify

- Fundamental reason a spread should hold; legging risk without intraday data

## Worst scenario (hedged is not risk-free)

- **This strategy:** several spreads break at once in a narrative rotation; the pairs share BTC and ETH legs, so they are fewer independent bets than six
- the relationship breaks and the spread never returns
- both legs gap together in a crash while the hedge ratio is stale
- short borrow is recalled or its rate jumps
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
