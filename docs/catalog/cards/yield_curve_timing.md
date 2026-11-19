# Yield-curve signal for equities

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `yield_curve_timing`
- **type:** [Global macro (discretionary and systematic)](../TYPES.md#global_macro)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Estrella Mishkin 1998 REStat
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Hold equities when 10y-3m spread > 0, else cash

Parameters (do not tune):

- `spread` = 10y minus 3m

**Data needed:** yields, equity TR

**Expected regime behaviour:** few signals per decades

## Known traps

- **Small sample / few independent bets** - Too few trades or independent observations for a significance claim. Monte-Neo: trade-count gate, dsr (existing).
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).
- **Discretionary / non-rule-based** - No reproducible rule; cannot be backtested honestly. Monte-Neo: not verifiable.

## How to measure

Metrics: Sharpe, regime-conditional return, beta to risk assets, hit rate, decision log.
Benchmark: Diversified risk-parity and trend indices.
Horizon: Full cycles; sparse independent macro events.

## What Monte-Neo cannot verify

- Discretionary judgement; revised macro data used as if known at the time
