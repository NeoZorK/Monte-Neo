# RSI(2) pullback

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `rsi2_connors`
- **type:** [Short-term mean reversion (single instrument)](../TYPES.md#mean_reversion)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Connors Alvarez 2008
- **verification (2026-11-08):** partial: rule shape confirmed in secondary sources (RSI2<10 or <5 variants, SMA200 filter, exit above SMA5); book text not read

## Definition (frozen, from the source)

Long when close > SMA(200) and RSI(2) < 10; exit when close > SMA(5)

Parameters (do not tune):

- `rsi` = 2
- `entry` = 10
- `trend` = 200
- `exit_sma` = 5

**Data needed:** daily close

**Expected regime behaviour:** buys dips in uptrends

## Known traps

- **Parameter overfitting** - Parameters tuned on the same sample used to report performance. Monte-Neo: pbo, holdout (existing).
- **Small sample / few independent bets** - Too few trades or independent observations for a significance claim. Monte-Neo: trade-count gate, dsr (existing).
- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).

## How to measure

Metrics: Win rate, payoff ratio, expectancy per trade, max adverse excursion, tail loss, time in market.
Benchmark: Buy-and-hold and a random-entry null with the same holding time.
Horizon: Many independent trades; drawdown clustered in trends.

## What Monte-Neo cannot verify

- Intraday excursion beyond daily bars
