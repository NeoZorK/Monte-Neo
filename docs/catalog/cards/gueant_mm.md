# Inventory-constrained market making

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `gueant_mm`
- **type:** [Market making / liquidity provision](../TYPES.md#market_making)
- **data tier:** C (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Gueant Lehalle Fernandez-Tapia 2013 Math. Financial Economics
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Quote bid and ask around mid with closed-form skew from inventory, risk aversion and order arrival intensity; hard inventory cap Q

Parameters (do not tune):

- `gamma` = 0.1
- `inventory_cap` = 10
- `arrival` = fitted A, k per day

**Data needed:** Level-2 quotes and trades

**Expected regime behaviour:** earns in range-bound flow; loses to informed flow in trends

## Known traps

- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).
- **Capacity / liquidity** - Strategy cannot be traded at size without moving the price. Monte-Neo: PLAN:capacity_estimate (volume participation).
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.

## How to measure

Metrics: Spread capture, adverse selection (markout), inventory risk, fill ratio, fees and rebates, latency sensitivity.
Benchmark: Zero; quoting at the touch with no skew.
Horizon: Intraday to weeks; many fills.

## What Monte-Neo cannot verify

- Queue position without full order-book data; daily bars are not enough

## Worst scenario (hedged is not risk-free)

- **This strategy:** a one-way move fills the full inventory cap on the wrong side (adverse selection) before quotes can move
- adverse selection: the quotes fill only on the side that keeps moving
- a gap through the inventory limit
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
