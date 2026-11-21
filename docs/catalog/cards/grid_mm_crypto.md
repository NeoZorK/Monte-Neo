# Crypto grid market making

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `grid_mm_crypto`
- **type:** [Market making / liquidity provision](../TYPES.md#market_making)
- **data tier:** C (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Exchange grid-bot practice; Avellaneda Stoikov 2008 for the inventory view
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Resting buy and sell orders every 0.5% around the starting price within a +-10% band; each fill re-posts the opposite order one step away

Parameters (do not tune):

- `step` = 0.005
- `band` = 0.1

**Data needed:** trade tape or 1-minute bars with high/low

**Expected regime behaviour:** profits in ranges; a breakout leaves full inventory at a loss

## Known traps

- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).
- **Look-ahead bias** - Signal uses information not available at decision time (same-bar close, restated data, future-dated fundamentals). Monte-Neo: lookahead (existing), data_integrity.

## How to measure

Metrics: Spread capture, adverse selection (markout), inventory risk, fill ratio, fees and rebates, latency sensitivity.
Benchmark: Zero; quoting at the touch with no skew.
Horizon: Intraday to weeks; many fills.

## What Monte-Neo cannot verify

- Queue position without full order-book data; daily bars are not enough

## Worst scenario (hedged is not risk-free)

- **This strategy:** price leaves the band and does not return: the grid holds its full inventory at the band edge
- adverse selection: the quotes fill only on the side that keeps moving
- a gap through the inventory limit
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
