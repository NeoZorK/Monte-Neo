# Convertible arbitrage (delta-hedged)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `convert_arb`
- **type:** [Convertible arbitrage](../TYPES.md#convertible_arb)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Agarwal Fung Loon Naik 2011
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long convertible, short delta shares; rehedge on 2% moves

Parameters (do not tune):

- `rehedge` = 0.02

**Data needed:** convertible prices, stock prices

**Expected regime behaviour:** 2008 liquidity crisis

## Known traps

- **Return smoothing / stale marks** - Serial correlation or stale prices understate volatility and inflate Sharpe. Monte-Neo: smoothing (existing, returns path).
- **Stale prices / illiquid quotes** - Last trade used as executable price in thin markets. Monte-Neo: data_integrity (partly).
- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.

## How to measure

Metrics: Net return, credit spread beta, liquidity-crisis drawdown, gamma P&L, smoothing of reported returns.
Benchmark: Credit and equity indices; hedge-fund index.
Horizon: Includes 2008 and 2020.

## What Monte-Neo cannot verify

- Reproducing a convertible book from public OHLCV; model-dependent marks

## Worst scenario (hedged is not risk-free)

- credit spreads widen and liquidity vanishes together (2005, 2008)
- short borrow on the stock is recalled
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
