# Dated-futures cash-and-carry basis

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `cash_and_carry`
- **type:** [Crypto-specific (perpetual funding, basis, cross-sectional crypto momentum)](../TYPES.md#crypto_specific)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Schmeling Schrimpf Todorov 2023
- **verification (2026-11-08):** partial: source paper exists (BIS WP 1087); min_basis_apr is ours, not from the paper

## Definition (frozen, from the source)

Long spot, short dated futures; hold to expiry; annualized basis > threshold

Parameters (do not tune):

- `min_basis_apr` = 0.05

**Data needed:** spot, futures prices

**Expected regime behaviour:** convergence at expiry

## Known traps

- **Funding rate and basis risk** - Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series. Monte-Neo: PLAN:carry_decomposition.
- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.

## How to measure

Metrics: Net of funding and fees, exchange-risk-adjusted return, drawdown, tail skew, capacity.
Benchmark: BTC/ETH buy-and-hold; stablecoin yield.
Horizon: Short history (2017+); covers few regimes.

## What Monte-Neo cannot verify

- Exchange insolvency
- depeg events outside the price series
