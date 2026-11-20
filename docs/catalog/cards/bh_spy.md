# Buy and hold equity index

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `bh_spy`
- **type:** [Buy-and-hold / passive cap-weighted index](../TYPES.md#passive_index)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Bogle 1976 (index fund idea); Sharpe 1991
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Hold 100% of the total-return index

Parameters (do not tune):

- `rebalance` = none

**Data needed:** daily total-return index or ETF

**Expected regime behaviour:** all; benchmark null

## Known traps

- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).
- **Corporate actions** - Splits, dividends and spin-offs not handled; adjusted vs unadjusted prices mixed. Monte-Neo: data_integrity (partly).

## How to measure

Metrics: CAGR, volatility, Sharpe, max drawdown, time under water, total-return series incl. dividends.
Benchmark: Itself; for others, the matching total-return index (equities) or spot asset (crypto).
Horizon: At least one full market cycle (10+ years for equities; crypto has under 2 full cycles).

## What Monte-Neo cannot verify

- Whether the sample period is representative; future returns
