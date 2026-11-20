# Variable moving-average 1/150

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `blb_ma_1_150`
- **type:** [Trend following / time-series momentum / CTA](../TYPES.md#trend_following)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Brock Lakonishok LeBaron 1992 JF
- **verification (2026-11-08):** partial: paper exists (J. Finance 47(5), 1731-1764, 1992; DJIA 1897-1986); the 1-150 rule and 1% band not confirmed

## Definition (frozen, from the source)

Long when price > SMA(150) by 1% band, short below

Parameters (do not tune):

- `slow` = 150
- `band` = 0.01

**Data needed:** daily close

**Expected regime behaviour:** original DJIA test 1897-1986

## Known traps

- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.
- **Post-publication decay** - Anomaly weakened after academic publication or crowding. Monte-Neo: PLAN:pre_post_publication_split.
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Sharpe, Sortino, convexity in equity down-markets (crisis alpha), beta to buy-and-hold, hit rate, payoff ratio, max drawdown.
Benchmark: Buy-and-hold of each asset; beta-neutral residual; equal-weight diversified trend index.
Horizon: Multi-decade, multi-asset; single-asset trend has few independent bets.

## What Monte-Neo cannot verify

- Diversification across markets when only one asset is supplied; futures margin details
