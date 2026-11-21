# Stablecoin peg arbitrage

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `stablecoin_depeg_arb`
- **type:** [Crypto-specific (perpetual funding, basis, cross-sectional crypto momentum)](../TYPES.md#crypto_specific)
- **data tier:** C (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Lyons Viswanath-Natraj 2023 JIMF 'What keeps stablecoins stable?'
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Buy a fiat-backed stablecoin below 0.995 and sell above 1.005 against USD, redeeming or minting at par where the account allows

Parameters (do not tune):

- `band` = 0.005

**Data needed:** stablecoin/USD quotes, redemption terms

**Expected regime behaviour:** mean reversion to the peg is the norm; a broken peg does not revert

## Known traps

- **Crash / momentum-crash risk** - Large drawdown clustered in market rebounds or crises. Monte-Neo: PLAN:tail_skew_profile.
- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Capacity / liquidity** - Strategy cannot be traded at size without moving the price. Monte-Neo: PLAN:capacity_estimate (volume participation).
- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).
- **Funding rate and basis risk** - Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series. Monte-Neo: PLAN:carry_decomposition.
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.

## How to measure

Metrics: Net of funding and fees, exchange-risk-adjusted return, drawdown, tail skew, capacity.
Benchmark: BTC/ETH buy-and-hold; stablecoin yield.
Horizon: Short history (2017+); covers few regimes.

## What Monte-Neo cannot verify

- Exchange insolvency
- depeg events outside the price series

## Worst scenario (hedged is not risk-free)

- **This strategy:** the peg breaks for good (an algorithmic stablecoin in 2022): the position is bought at 0.99 and ends near zero
- the venue halts withdrawals or fails
- a peg, a listing or a relationship that held in the sample breaks for good
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
