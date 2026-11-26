# Post-earnings announcement drift

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `pead`
- **type:** [Merger arbitrage and event-driven](../TYPES.md#event_merger_arb)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Ball Brown 1968; Bernard Thomas 1989 JAR
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long top decile standardized earnings surprise, short bottom; hold 60 days

Parameters (do not tune):

- `hold_days` = 60
- `deciles` = 10

**Data needed:** earnings dates and estimates

**Expected regime behaviour:** decayed

## Known traps

- **Point-in-time fundamentals** - Fundamentals used with their period-end date instead of their publication date, or restated. Monte-Neo: PLAN:pit_contract (data validator).
- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Post-publication decay** - Anomaly weakened after academic publication or crowding. Monte-Neo: PLAN:pre_post_publication_split.
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
