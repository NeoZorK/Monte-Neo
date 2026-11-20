# Equity collar (CLL style)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `collar_cll`
- **type:** [Options overlays (covered call, put-write, collar, protective put)](../TYPES.md#options_overlay)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** CBOE CLL index methodology
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Hold index, buy 5% OTM put, sell 10% OTM call

Parameters (do not tune):

- `put_otm` = 0.05
- `call_otm` = 0.1

**Data needed:** index, option chains

**Expected regime behaviour:** limited upside and downside

## Known traps

- **Unrealistic execution model** - Fills at mid, no queue position, no partial fills, no latency. Monte-Neo: verify_quotes (existing, intraday quotes).
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).

## How to measure

Metrics: Return vs underlying at matched beta, upside capture, downside capture, Sharpe, drawdown.
Benchmark: Underlying total-return index; beta-matched equity plus cash.
Horizon: Full cycle including a strong rally and a crash.

## What Monte-Neo cannot verify

- Fills at mid; early exercise; the tax treatment
