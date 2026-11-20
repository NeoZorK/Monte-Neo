# Cash-secured put-write (PUT index)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `put_write`
- **type:** [Options overlays (covered call, put-write, collar, protective put)](../TYPES.md#options_overlay)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Bondarenko 2014; CBOE PUT
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Sell ATM one-month put collateralized with T-bills

Parameters (do not tune):

- `tenor` = 1 month
- `moneyness` = ATM

**Data needed:** index, option chains

**Expected regime behaviour:** short vol

## Known traps

- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.

## How to measure

Metrics: Return vs underlying at matched beta, upside capture, downside capture, Sharpe, drawdown.
Benchmark: Underlying total-return index; beta-matched equity plus cash.
Horizon: Full cycle including a strong rally and a crash.

## What Monte-Neo cannot verify

- Fills at mid; early exercise; the tax treatment
