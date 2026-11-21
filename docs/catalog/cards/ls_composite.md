# Long/short equity multi-factor composite

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `ls_composite`
- **type:** [Long/short equity](../TYPES.md#long_short_equity)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Fama French 2015; Asness et al. 2013 JF
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Equal-weight z-scores of value, momentum, quality; long top decile, short bottom; dollar-neutral

Parameters (do not tune):

- `deciles` = 10

**Data needed:** PIT fundamentals, borrow costs

**Expected regime behaviour:** market-neutral

## Known traps

- **Short-sale cost and availability** - Borrow fees, locates and recalls are ignored for the short leg. Monte-Neo: PLAN:borrow_model.
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).

## How to measure

Metrics: Net and gross exposure, beta, alpha, short-leg contribution, borrow cost, turnover.
Benchmark: Market, sector, and factor returns.
Horizon: Multi-year, includes crashes.

## What Monte-Neo cannot verify

- Stock-picking skill from narrative; locates and recalls

## Worst scenario (hedged is not risk-free)

- the long and short books fall together in a deleveraging (August 2007 quant crisis)
- a short squeeze on a crowded short
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
