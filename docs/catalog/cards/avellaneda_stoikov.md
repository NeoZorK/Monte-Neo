# Avellaneda-Stoikov market making

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `avellaneda_stoikov`
- **type:** [Market making / liquidity provision](../TYPES.md#market_making)
- **data tier:** C (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Avellaneda Stoikov 2008
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Quote around reservation price r = s - q*gamma*sigma^2*(T-t) with optimal spread

Parameters (do not tune):

- `gamma` = 0.1
- `k` = 1.5

**Data needed:** L2 quotes and trades

**Expected regime behaviour:** needs microstructure data

## Known traps

- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).
- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.
- **Capacity / liquidity** - Strategy cannot be traded at size without moving the price. Monte-Neo: PLAN:capacity_estimate (volume participation).

## How to measure

Metrics: Spread capture, adverse selection (markout), inventory risk, fill ratio, fees and rebates, latency sensitivity.
Benchmark: Zero; quoting at the touch with no skew.
Horizon: Intraday to weeks; many fills.

## What Monte-Neo cannot verify

- Queue position without full order-book data; daily bars are not enough
