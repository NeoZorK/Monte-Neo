# Bollinger band breakout

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `bollinger_breakout`
- **type:** [Trend following / time-series momentum / CTA](../TYPES.md#trend_following)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Bollinger 2001
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long when close > upper band (20, 2)

Parameters (do not tune):

- `window` = 20
- `k` = 2.0

**Data needed:** daily close

**Expected regime behaviour:** trend

## Known traps

- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Sharpe, Sortino, convexity in equity down-markets (crisis alpha), beta to buy-and-hold, hit rate, payoff ratio, max drawdown.
Benchmark: Buy-and-hold of each asset; beta-neutral residual; equal-weight diversified trend index.
Horizon: Multi-decade, multi-asset; single-asset trend has few independent bets.

## What Monte-Neo cannot verify

- Diversification across markets when only one asset is supplied; futures margin details
