# Global equities momentum (dual momentum)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `dual_momentum_gem`
- **type:** [Trend following / time-series momentum / CTA](../TYPES.md#trend_following)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Antonacci 2014 Dual Momentum Investing
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Each month: if US equity 12m return > T-bill, hold the stronger of US vs ex-US equity; else bonds

Parameters (do not tune):

- `lookback_months` = 12

**Data needed:** US equity, ex-US equity, bond, T-bill

**Expected regime behaviour:** few trades; one switch every ~1 year

## Known traps

- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.
- **Small sample / few independent bets** - Too few trades or independent observations for a significance claim. Monte-Neo: trade-count gate, dsr (existing).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Sharpe, Sortino, convexity in equity down-markets (crisis alpha), beta to buy-and-hold, hit rate, payoff ratio, max drawdown.
Benchmark: Buy-and-hold of each asset; beta-neutral residual; equal-weight diversified trend index.
Horizon: Multi-decade, multi-asset; single-asset trend has few independent bets.

## What Monte-Neo cannot verify

- Diversification across markets when only one asset is supplied; futures margin details
