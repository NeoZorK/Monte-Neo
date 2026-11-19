# Crypto perpetual funding carry

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `crypto_funding_carry`
- **type:** [Crypto-specific (perpetual funding, basis, cross-sectional crypto momentum)](../TYPES.md#crypto_specific)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Schmeling Schrimpf Todorov 2023 BIS WP 1087
- **verification (2026-11-08):** partial: source paper exists (BIS WP 1087, 2023-04-04); thresholds in params are ours, not from the paper

## Definition (frozen, from the source)

Long spot, short perpetual when funding rate > 0; delta-neutral

Parameters (do not tune):

- `min_funding_apr` = 0.1
- `rebalance` = daily

**Data needed:** spot, perp prices, funding history

**Expected regime behaviour:** positive in bulls; basis blowups

## Known traps

- **Funding rate and basis risk** - Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series. Monte-Neo: PLAN:carry_decomposition.
- **Leverage and margin** - Reported return relies on leverage that is unavailable or can trigger liquidation. Monte-Neo: PLAN:leverage_audit.
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Small sample / few independent bets** - Too few trades or independent observations for a significance claim. Monte-Neo: trade-count gate, dsr (existing).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.

## How to measure

Metrics: Net of funding and fees, exchange-risk-adjusted return, drawdown, tail skew, capacity.
Benchmark: BTC/ETH buy-and-hold; stablecoin yield.
Horizon: Short history (2017+); covers few regimes.

## What Monte-Neo cannot verify

- Exchange insolvency
- depeg events outside the price series
