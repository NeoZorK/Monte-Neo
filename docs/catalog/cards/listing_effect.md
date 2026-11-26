# Exchange listing announcement effect

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `listing_effect`
- **type:** [Merger arbitrage and event-driven](../TYPES.md#event_merger_arb)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Event-study literature on crypto exchange listings
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Buy a coin at the first daily close after a major-exchange listing announcement, sell 5 days later

Parameters (do not tune):

- `hold_days` = 5

**Data needed:** announcement timestamps, daily OHLCV

**Expected regime behaviour:** most of the move happens in minutes after the announcement

## Known traps

- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Execution timing** - Trade assumed at the close/open that generated the signal. Monte-Neo: lookahead, timing (existing).
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.

## How to measure

Metrics: Annualized spread return, deal-break loss, hit rate, correlation to market in down-markets, event study CARs.
Benchmark: Market and risk-free rate; hedge-fund merger arb index.
Horizon: Includes a merger-boom and a bust; deal-level sample size.

## What Monte-Neo cannot verify

- Legal and regulatory risk; deal-specific information

## Worst scenario (hedged is not risk-free)

- the deal breaks: the target falls back to its stand-alone price, many times the spread earned
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
