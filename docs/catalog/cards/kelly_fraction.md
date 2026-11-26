# Fractional Kelly sizing

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `kelly_fraction`
- **type:** [Rebalancing and glide-path policies (constant-mix, CPPI, target-date)](../TYPES.md#rebalancing_policy)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Kelly 1956; Thorp 2006 (Handbook of Asset and Liability Management)
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Exposure = 0.5 x (expected excess return / variance) from 252-day estimates, capped at 2x; daily

Parameters (do not tune):

- `fraction` = 0.5
- `window` = 252
- `cap` = 2.0

**Data needed:** daily returns, risk-free rate

**Expected regime behaviour:** estimation error makes full Kelly ruinous; half Kelly is the usual compromise

## Known traps

- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.
- **Parameter overfitting** - Parameters tuned on the same sample used to report performance. Monte-Neo: pbo, holdout (existing).
- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Rebalancing convention** - Result depends on rebalance frequency, thresholds and whether drift or costs are modelled. Monte-Neo: PLAN:rebalance_sensitivity.
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Terminal wealth distribution, shortfall probability, path dependence, turnover, cost drag.
Benchmark: Buy-and-hold with the same initial weights.
Horizon: Investor lifetime; needs simulated and historical paths.

## What Monte-Neo cannot verify

- Investor behaviour; the tax and lifetime-income context
