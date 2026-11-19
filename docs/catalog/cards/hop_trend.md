# Multi-horizon trend (1/3/12 month)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `hop_trend`
- **type:** [Trend following / time-series momentum / CTA](../TYPES.md#trend_following)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Hurst Ooi Pedersen 2017 JPM
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Equal-weight sign of 1, 3, 12 month returns, vol-scaled

Parameters (do not tune):

- `lookbacks_months` = [1, 3, 12]
- `vol_target` = 0.1

**Data needed:** daily futures or spot

**Expected regime behaviour:** century-long evidence; diversified markets

## Known traps

- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Parameter overfitting** - Parameters tuned on the same sample used to report performance. Monte-Neo: pbo, holdout (existing).
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Sharpe, Sortino, convexity in equity down-markets (crisis alpha), beta to buy-and-hold, hit rate, payoff ratio, max drawdown.
Benchmark: Buy-and-hold of each asset; beta-neutral residual; equal-weight diversified trend index.
Horizon: Multi-decade, multi-asset; single-asset trend has few independent bets.

## What Monte-Neo cannot verify

- Diversification across markets when only one asset is supplied; futures margin details
