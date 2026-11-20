# Time-series momentum long/flat 12m

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `tsmom_long_only`
- **type:** [Trend following / time-series momentum / CTA](../TYPES.md#trend_following)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Moskowitz Ooi Pedersen 2012; long-only variant
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long if past 12-month return > 0 else cash

Parameters (do not tune):

- `lookback_months` = 12

**Data needed:** daily spot

**Expected regime behaviour:** avoids major bear markets with lag

## Known traps

- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Sharpe, Sortino, convexity in equity down-markets (crisis alpha), beta to buy-and-hold, hit rate, payoff ratio, max drawdown.
Benchmark: Buy-and-hold of each asset; beta-neutral residual; equal-weight diversified trend index.
Horizon: Multi-decade, multi-asset; single-asset trend has few independent bets.

## What Monte-Neo cannot verify

- Diversification across markets when only one asset is supplied; futures margin details
