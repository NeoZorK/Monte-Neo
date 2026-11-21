# VPIN toxicity filter

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `vpin_filter`
- **type:** [Order flow and microstructure signals](../TYPES.md#order_flow)
- **data tier:** C (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Easley Lopez de Prado O'Hara 2012 RFS
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Volume-synchronized probability of informed trading over 50 buckets; withdraw liquidity or cut exposure above its 90th percentile

Parameters (do not tune):

- `buckets` = 50
- `cut_pct` = 90

**Data needed:** trade tape with volumes

**Expected regime behaviour:** a risk filter, not a return source; contested evidence

## Known traps

- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.
- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).

## How to measure

Metrics: Net Sharpe after fees and spread, markout by horizon, hit rate, turnover, latency sensitivity.
Benchmark: Zero; random entry with the same holding time.
Horizon: Seconds to hours; many trades; out-of-sample days separated.

## What Monte-Neo cannot verify

- Queue position and hidden liquidity without full message data; daily bars are not enough

## Worst scenario (hedged is not risk-free)

- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
