# Cumulative RSI(2)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `cum_rsi2`
- **type:** [Short-term mean reversion (single instrument)](../TYPES.md#mean_reversion)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Connors Alvarez 2008
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long when 2-day sum of RSI(2) < 35 and close > SMA(200); exit RSI(2) > 65

Parameters (do not tune):

- `sum_days` = 2
- `entry` = 35
- `exit` = 65

**Data needed:** daily close

**Expected regime behaviour:** dip buying

## Known traps

- **Parameter overfitting** - Parameters tuned on the same sample used to report performance. Monte-Neo: pbo, holdout (existing).
- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).

## How to measure

Metrics: Win rate, payoff ratio, expectancy per trade, max adverse excursion, tail loss, time in market.
Benchmark: Buy-and-hold and a random-entry null with the same holding time.
Horizon: Many independent trades; drawdown clustered in trends.

## What Monte-Neo cannot verify

- Intraday excursion beyond daily bars
