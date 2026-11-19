# Crypto time-series momentum

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `crypto_tsmom`
- **type:** [Crypto-specific (perpetual funding, basis, cross-sectional crypto momentum)](../TYPES.md#crypto_specific)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Liu Tsyvinski 2021 RFS
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Long when past 4-week return > 0

Parameters (do not tune):

- `lookback_weeks` = 4

**Data needed:** BTC/ETH daily

**Expected regime behaviour:** crypto bull cycles

## Known traps

- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Small sample / few independent bets** - Too few trades or independent observations for a significance claim. Monte-Neo: trade-count gate, dsr (existing).
- **Funding rate and basis risk** - Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series. Monte-Neo: PLAN:carry_decomposition.

## How to measure

Metrics: Net of funding and fees, exchange-risk-adjusted return, drawdown, tail skew, capacity.
Benchmark: BTC/ETH buy-and-hold; stablecoin yield.
Horizon: Short history (2017+); covers few regimes.

## What Monte-Neo cannot verify

- Exchange insolvency
- depeg events outside the price series
