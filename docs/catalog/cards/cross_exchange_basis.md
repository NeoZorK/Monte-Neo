# Cross-exchange price arbitrage

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `cross_exchange_basis`
- **type:** [Crypto-specific (perpetual funding, basis, cross-sectional crypto momentum)](../TYPES.md#crypto_specific)
- **data tier:** C (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Makarov Schoar 2020 JFE 'Trading and arbitrage in cryptocurrency markets'
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Buy the coin on the venue where it is cheaper and sell it where it is dearer when the gap net of fees and transfer cost exceeds a threshold; inventory held on both venues

Parameters (do not tune):

- `threshold_bps` = fees + transfer cost + 10
- `inventory` = both venues pre-funded

**Data needed:** synchronous order books of two venues, withdrawal fees and times

**Expected regime behaviour:** gaps were large in 2017-2018 and where capital controls bind; small and fleeting on liquid venues

## Known traps

- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).
- **Capacity / liquidity** - Strategy cannot be traded at size without moving the price. Monte-Neo: PLAN:capacity_estimate (volume participation).
- **Stale prices / illiquid quotes** - Last trade used as executable price in thin markets. Monte-Neo: data_integrity (partly).
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
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

- **This strategy:** one venue halts withdrawals or fails while it holds half of the inventory; transfers are delayed when the gap is widest
- the venue halts withdrawals or fails
- a peg, a listing or a relationship that held in the sample breaks for good
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
