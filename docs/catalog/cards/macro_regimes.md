# Growth/inflation regime allocation

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `macro_regimes`
- **type:** [Global macro (discretionary and systematic)](../TYPES.md#global_macro)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Bridgewater public quadrant framework; rule proxy by us
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Rising/falling growth x inflation from released data; hold regime-favored assets

Parameters (do not tune):

- `growth` = real GDP nowcast sign
- `inflation` = CPI trend sign

**Data needed:** PIT macro releases, asset returns

**Expected regime behaviour:** proxy, not a replication

## Known traps

- **Point-in-time fundamentals** - Fundamentals used with their period-end date instead of their publication date, or restated. Monte-Neo: PLAN:pit_contract (data validator).
- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.
- **Discretionary / non-rule-based** - No reproducible rule; cannot be backtested honestly. Monte-Neo: not verifiable.
- **Small sample / few independent bets** - Too few trades or independent observations for a significance claim. Monte-Neo: trade-count gate, dsr (existing).

## How to measure

Metrics: Sharpe, regime-conditional return, beta to risk assets, hit rate, decision log.
Benchmark: Diversified risk-parity and trend indices.
Horizon: Full cycles; sparse independent macro events.

## What Monte-Neo cannot verify

- Discretionary judgement; revised macro data used as if known at the time
