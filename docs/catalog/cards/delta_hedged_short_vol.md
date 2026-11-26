# Delta-hedged short straddle (variance risk premium)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `delta_hedged_short_vol`
- **type:** [Volatility selling / short vol](../TYPES.md#short_volatility)
- **data tier:** C (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Carr Wu 2009 RFS 'Variance risk premiums'
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Sell a 30-day at-the-money straddle on BTC options each month and hedge its delta daily with the perpetual; size to 10% annual vol of the book

Parameters (do not tune):

- `tenor_days` = 30
- `hedge` = daily
- `vol_target` = 0.1

**Data needed:** option quotes and implied vol, perpetual closes

**Expected regime behaviour:** earns in calm markets; a vol spike can take years of premium

## Known traps

- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Crash / momentum-crash risk** - Large drawdown clustered in market rebounds or crises. Monte-Neo: PLAN:tail_skew_profile.
- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).
- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Return smoothing / stale marks** - Serial correlation or stale prices understate volatility and inflate Sharpe. Monte-Neo: smoothing (existing, returns path).

## How to measure

Metrics: Skew, kurtosis, CVaR 1%/5%, worst day/month, Sharpe adjusted for skew (e.g. Sortino, Omega), time to recover, stress replays (Feb 2018 XIV, Mar 2020).
Benchmark: Equity index; put-write index; cash.
Horizon: Must include a vol-spike event; otherwise the sample is uninformative.

## What Monte-Neo cannot verify

- Gap and liquidity events not in the sample; early assignment details with daily data

## Worst scenario (hedged is not risk-free)

- **This strategy:** a gap move larger than the daily hedge can follow: the straddle loses many times the monthly premium (short-volatility tail)
- a volatility spike larger than any in the sample: years of premium lost in days
- margin calls force closing at the worst prices
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
