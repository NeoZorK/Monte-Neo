# Passive rebate capture at the touch

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `rebate_capture`
- **type:** [Market making / liquidity provision](../TYPES.md#market_making)
- **data tier:** C (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Maker-taker pricing literature; Foucault Kadan Kandel 2013 JF
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Join the best bid and ask only when queue position is in the front third; cancel when the opposite side thins

Parameters (do not tune):

- `queue_front` = 0.33

**Data needed:** full order-book messages with queue position

**Expected regime behaviour:** depends on fee tier and latency rank

## Known traps

- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).
- **Capacity / liquidity** - Strategy cannot be traded at size without moving the price. Monte-Neo: PLAN:capacity_estimate (volume participation).
- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.

## How to measure

Metrics: Spread capture, adverse selection (markout), inventory risk, fill ratio, fees and rebates, latency sensitivity.
Benchmark: Zero; quoting at the touch with no skew.
Horizon: Intraday to weeks; many fills.

## What Monte-Neo cannot verify

- Queue position without full order-book data; daily bars are not enough

## Worst scenario (hedged is not risk-free)

- **This strategy:** fills arrive only before adverse moves (markout negative) and the rebate does not cover it
- adverse selection: the quotes fill only on the side that keeps moving
- a gap through the inventory limit
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
