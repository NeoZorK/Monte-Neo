# Elastic asset allocation

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `eaa_keller`
- **type:** [Trend following / time-series momentum / CTA](../TYPES.md#trend_following)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Keller Putten 2012 SSRN 2543979
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Score = return^wR * (1 - correlation)^wC / vol^wV on momentum windows; choose top N

Parameters (do not tune):

- `wR` = 1
- `wC` = 1
- `wV` = 0
- `top` = 5

**Data needed:** multi-asset ETFs

**Expected regime behaviour:** tactical allocation

## Known traps

- **Parameter overfitting** - Parameters tuned on the same sample used to report performance. Monte-Neo: pbo, holdout (existing).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Sharpe, Sortino, convexity in equity down-markets (crisis alpha), beta to buy-and-hold, hit rate, payoff ratio, max drawdown.
Benchmark: Buy-and-hold of each asset; beta-neutral residual; equal-weight diversified trend index.
Horizon: Multi-decade, multi-asset; single-asset trend has few independent bets.

## What Monte-Neo cannot verify

- Diversification across markets when only one asset is supplied; futures margin details
