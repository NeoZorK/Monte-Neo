# Ivy portfolio (5 asset trend filter)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `ivy_five`
- **type:** [Trend following / time-series momentum / CTA](../TYPES.md#trend_following)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Faber 2007 SSRN 962461 / 2009 The Ivy Portfolio
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Equal weight US stocks, foreign stocks, bonds, REITs, commodities; hold each only when price > 10-month SMA at month end

Parameters (do not tune):

- `sma_months` = 10
- `rebalance` = monthly

**Data needed:** 5 monthly or daily series

**Expected regime behaviour:** reduces drawdowns in bear markets, lags in whipsaw

## Known traps

- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Execution timing** - Trade assumed at the close/open that generated the signal. Monte-Neo: lookahead, timing (existing).
- **Small sample / few independent bets** - Too few trades or independent observations for a significance claim. Monte-Neo: trade-count gate, dsr (existing).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Sharpe, Sortino, convexity in equity down-markets (crisis alpha), beta to buy-and-hold, hit rate, payoff ratio, max drawdown.
Benchmark: Buy-and-hold of each asset; beta-neutral residual; equal-weight diversified trend index.
Horizon: Multi-decade, multi-asset; single-asset trend has few independent bets.

## What Monte-Neo cannot verify

- Diversification across markets when only one asset is supplied; futures margin details
