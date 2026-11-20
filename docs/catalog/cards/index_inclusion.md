# S&P 500 inclusion effect

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `index_inclusion`
- **type:** [Merger arbitrage and event-driven](../TYPES.md#event_merger_arb)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Shleifer 1986; Harris Gurel 1986 JF
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long announced additions, exit at effective date

Parameters (do not tune):

- `window` = announcement to effective date

**Data needed:** index change announcements

**Expected regime behaviour:** mostly arbitraged away

## Known traps

- **Post-publication decay** - Anomaly weakened after academic publication or crowding. Monte-Neo: PLAN:pre_post_publication_split.
- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.

## How to measure

Metrics: Annualized spread return, deal-break loss, hit rate, correlation to market in down-markets, event study CARs.
Benchmark: Market and risk-free rate; hedge-fund merger arb index.
Horizon: Includes a merger-boom and a bust; deal-level sample size.

## What Monte-Neo cannot verify

- Legal and regulatory risk; deal-specific information
