# Short VIX futures roll

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `short_vix_futures`
- **type:** [Volatility selling / short vol](../TYPES.md#short_volatility)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Variance risk premium: Carr Wu 2009
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Short front-month VIX futures when curve in contango, flat otherwise

Parameters (do not tune):

- `signal` = front vs spot basis > 0

**Data needed:** VIX futures curve

**Expected regime behaviour:** Feb 2018 loss

## Known traps

- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Futures roll yield** - Continuous contract built by naive stitching hides roll cost or gain. Monte-Neo: PLAN:roll_audit.
- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Return smoothing / stale marks** - Serial correlation or stale prices understate volatility and inflate Sharpe. Monte-Neo: smoothing (existing, returns path).

## How to measure

Metrics: Skew, kurtosis, CVaR 1%/5%, worst day/month, Sharpe adjusted for skew (e.g. Sortino, Omega), time to recover, stress replays (Feb 2018 XIV, Mar 2020).
Benchmark: Equity index; put-write index; cash.
Horizon: Must include a vol-spike event; otherwise the sample is uninformative.

## What Monte-Neo cannot verify

- Gap and liquidity events not in the sample; early assignment details with daily data

## Worst scenario (hedged is not risk-free)

- a volatility spike larger than any in the sample: years of premium lost in days
- margin calls force closing at the worst prices
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
