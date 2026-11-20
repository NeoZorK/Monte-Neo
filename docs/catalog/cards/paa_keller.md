# Protective asset allocation

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `paa_keller`
- **type:** [Trend following / time-series momentum / CTA](../TYPES.md#trend_following)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Keller Keuning 2016 SSRN 2759734
- **verification (2026-11-08):** partial: paper exists (SSRN 2759734, 2016-04-25); formula corrected to SMA12 filter per later Keller-Keuning description; top-N and protection level unverified

## Definition (frozen, from the source)

Per asset, momentum filter on price relative to its 12-month SMA; the fraction held in the safe asset rises with the number of assets failing the filter

Parameters (do not tune):

- `sma_months` = 12
- `top_n` = unverified
- `protection_level` = unverified (low/medium/high in paper)

**Data needed:** 12-asset ETF universe

**Expected regime behaviour:** tactical allocation

## Known traps

- **Parameter overfitting** - Parameters tuned on the same sample used to report performance. Monte-Neo: pbo, holdout (existing).
- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Sharpe, Sortino, convexity in equity down-markets (crisis alpha), beta to buy-and-hold, hit rate, payoff ratio, max drawdown.
Benchmark: Buy-and-hold of each asset; beta-neutral residual; equal-weight diversified trend index.
Horizon: Multi-decade, multi-asset; single-asset trend has few independent bets.

## What Monte-Neo cannot verify

- Diversification across markets when only one asset is supplied; futures margin details
