# Global carry across asset classes

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `global_carry`
- **type:** [Carry (FX, commodity roll, bond roll-down, crypto funding/basis)](../TYPES.md#carry)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Koijen Moskowitz Pedersen Vrugt 2018 JFE
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Position proportional to carry in each asset class

Parameters (do not tune):

- `scaling` = inverse vol

**Data needed:** futures prices and carry measures

**Expected regime behaviour:** multi-asset

## Known traps

- **Futures roll yield** - Continuous contract built by naive stitching hides roll cost or gain. Monte-Neo: PLAN:roll_audit.
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Funding rate and basis risk** - Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series. Monte-Neo: PLAN:carry_decomposition.

## How to measure

Metrics: Carry return vs spot return decomposition, Sharpe, skew, crash drawdowns, funding sign flips, margin usage.
Benchmark: Spot/buy-and-hold; cash.
Horizon: Includes a crisis (2008 FX, 2020 and 2022 crypto).

## What Monte-Neo cannot verify

- Counterparty/exchange default; margin calls from intraday spikes
