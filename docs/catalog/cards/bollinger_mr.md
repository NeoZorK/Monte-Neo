# Bollinger mean reversion

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `bollinger_mr`
- **type:** [Short-term mean reversion (single instrument)](../TYPES.md#mean_reversion)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Bollinger 2001
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long when close < lower band (20, 2); exit at middle band

Parameters (do not tune):

- `window` = 20
- `k` = 2.0

**Data needed:** daily close

**Expected regime behaviour:** range markets

## Known traps

- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).

## How to measure

Metrics: Win rate, payoff ratio, expectancy per trade, max adverse excursion, tail loss, time in market.
Benchmark: Buy-and-hold and a random-entry null with the same holding time.
Horizon: Many independent trades; drawdown clustered in trends.

## What Monte-Neo cannot verify

- Intraday excursion beyond daily bars
