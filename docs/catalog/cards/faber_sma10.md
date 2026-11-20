# Faber 10-month SMA timing

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `faber_sma10`
- **type:** [Trend following / time-series momentum / CTA](../TYPES.md#trend_following)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Faber 2007 JWM
- **verification (2026-11-08):** confirmed-secondary: 10-month SMA, five asset classes equal weight, cash when out (summaries, 2026-11-08); primary text not read

## Definition (frozen, from the source)

Hold asset if month-end price > 10-month SMA else cash

Parameters (do not tune):

- `sma_months` = 10

**Data needed:** monthly or daily close

**Expected regime behaviour:** drawdown reduction

## Known traps

- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Execution timing** - Trade assumed at the close/open that generated the signal. Monte-Neo: lookahead, timing (existing).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Sharpe, Sortino, convexity in equity down-markets (crisis alpha), beta to buy-and-hold, hit rate, payoff ratio, max drawdown.
Benchmark: Buy-and-hold of each asset; beta-neutral residual; equal-weight diversified trend index.
Horizon: Multi-decade, multi-asset; single-asset trend has few independent bets.

## What Monte-Neo cannot verify

- Diversification across markets when only one asset is supplied; futures margin details
