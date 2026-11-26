# Order-book imbalance signal

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `obi_signal`
- **type:** [Order flow and microstructure signals](../TYPES.md#order_flow)
- **data tier:** C (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Cont Kukanov Stoikov 2014 J. Financial Econometrics
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Order flow imbalance over the last 10 seconds; enter in its direction when above 2 standard deviations, exit after 30 seconds

Parameters (do not tune):

- `window_s` = 10
- `threshold_sd` = 2.0
- `hold_s` = 30

**Data needed:** Level-1 quote updates with exchange timestamps

**Expected regime behaviour:** a forecast of seconds; costs and latency decide

## Known traps

- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.

## How to measure

Metrics: Net Sharpe after fees and spread, markout by horizon, hit rate, turnover, latency sensitivity.
Benchmark: Zero; random entry with the same holding time.
Horizon: Seconds to hours; many trades; out-of-sample days separated.

## What Monte-Neo cannot verify

- Queue position and hidden liquidity without full message data; daily bars are not enough

## Worst scenario (hedged is not risk-free)

- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
