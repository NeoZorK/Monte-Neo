# Internal bar strength

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `ibs`
- **type:** [Short-term mean reversion (single instrument)](../TYPES.md#mean_reversion)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Connors / Alvarez-era retail literature; no peer-reviewed source
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long when (close-low)/(high-low) < 0.2; exit next close

Parameters (do not tune):

- `threshold` = 0.2

**Data needed:** daily OHLC

**Expected regime behaviour:** index ETFs

## Known traps

- **Execution timing** - Trade assumed at the close/open that generated the signal. Monte-Neo: lookahead, timing (existing).
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.
- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).

## How to measure

Metrics: Win rate, payoff ratio, expectancy per trade, max adverse excursion, tail loss, time in market.
Benchmark: Buy-and-hold and a random-entry null with the same holding time.
Horizon: Many independent trades; drawdown clustered in trends.

## What Monte-Neo cannot verify

- Intraday excursion beyond daily bars
