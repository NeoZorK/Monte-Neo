# Volatility-scaled trend with 10% target

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `tail_trend_vol_scaled`
- **type:** [Trend following / time-series momentum / CTA](../TYPES.md#trend_following)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Baltas Kosowski 2013; Kim Tse Wald 2016
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

sign(12m return) * 10% / EWMA vol (60-day)

Parameters (do not tune):

- `lookback_months` = 12
- `vol_target` = 0.1
- `ewma_days` = 60

**Data needed:** daily futures or spot

**Expected regime behaviour:** diversified trend

## Known traps

- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Sharpe, Sortino, convexity in equity down-markets (crisis alpha), beta to buy-and-hold, hit rate, payoff ratio, max drawdown.
Benchmark: Buy-and-hold of each asset; beta-neutral residual; equal-weight diversified trend index.
Horizon: Multi-decade, multi-asset; single-asset trend has few independent bets.

## What Monte-Neo cannot verify

- Diversification across markets when only one asset is supplied; futures margin details
