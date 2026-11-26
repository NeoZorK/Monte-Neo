# MVRV on-chain valuation timing

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `mvrv_onchain`
- **type:** [Crypto-specific (perpetual funding, basis, cross-sectional crypto momentum)](../TYPES.md#crypto_specific)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Mahmudov Puell 2018 (MVRV ratio); on-chain analytics literature
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Hold BTC when the market-to-realized-value ratio is below 3.5, sell to cash above 3.7

Parameters (do not tune):

- `buy_below` = 3.5
- `sell_above` = 3.7

**Data needed:** daily realized capitalization from on-chain data

**Expected regime behaviour:** few cycles in the sample; thresholds chosen after the fact by many

## Known traps

- **Small sample / few independent bets** - Too few trades or independent observations for a significance claim. Monte-Neo: trade-count gate, dsr (existing).
- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.
- **Vendor / index construction effects** - Result depends on a proprietary index methodology or vendor-specific adjustment. Monte-Neo: not verifiable.
- **Funding rate and basis risk** - Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series. Monte-Neo: PLAN:carry_decomposition.
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.

## How to measure

Metrics: Net of funding and fees, exchange-risk-adjusted return, drawdown, tail skew, capacity.
Benchmark: BTC/ETH buy-and-hold; stablecoin yield.
Horizon: Short history (2017+); covers few regimes.

## What Monte-Neo cannot verify

- Exchange insolvency
- depeg events outside the price series
