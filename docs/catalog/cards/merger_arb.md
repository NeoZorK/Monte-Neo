# Merger arbitrage spread

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `merger_arb`
- **type:** [Merger arbitrage and event-driven](../TYPES.md#event_merger_arb)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Mitchell Pulvino 2001 JF
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long targets of announced cash deals, hold to close, equal weight

Parameters (do not tune):

- `min_spread` = annualized 5%

**Data needed:** deal database, prices

**Expected regime behaviour:** deal-break tail

## Known traps

- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Capacity / liquidity** - Strategy cannot be traded at size without moving the price. Monte-Neo: PLAN:capacity_estimate (volume participation).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.

## How to measure

Metrics: Annualized spread return, deal-break loss, hit rate, correlation to market in down-markets, event study CARs.
Benchmark: Market and risk-free rate; hedge-fund merger arb index.
Horizon: Includes a merger-boom and a bust; deal-level sample size.

## What Monte-Neo cannot verify

- Legal and regulatory risk; deal-specific information
