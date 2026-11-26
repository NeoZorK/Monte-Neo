# Cross-sectional funding carry (dollar-neutral)

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `funding_xs_neutral`
- **type:** [Carry (FX, commodity roll, bond roll-down, crypto funding/basis)](../TYPES.md#carry)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Schmeling Schrimpf Todorov 2023 'Crypto carry' (BIS Working Paper 1087)
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Rank perpetuals by trailing 7-day mean funding; long the lowest third, short the highest third, dollar-neutral; weekly

Parameters (do not tune):

- `lookback_days` = 7
- `quantiles` = 3
- `rebalance` = weekly

**Data needed:** perpetual daily closes and funding of 12+ coins

**Expected regime behaviour:** high-funding coins are crowded longs; the short side can squeeze in a mania

## Known traps

- **Funding rate and basis risk** - Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series. Monte-Neo: PLAN:carry_decomposition.
- **Crash / momentum-crash risk** - Large drawdown clustered in market rebounds or crises. Monte-Neo: PLAN:tail_skew_profile.
- **Short-sale cost and availability** - Borrow fees, locates and recalls are ignored for the short leg. Monte-Neo: PLAN:borrow_model.
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).

## How to measure

Metrics: Carry return vs spot return decomposition, Sharpe, skew, crash drawdowns, funding sign flips, margin usage.
Benchmark: Spot/buy-and-hold; cash.
Horizon: Includes a crisis (2008 FX, 2020 and 2022 crypto).

## What Monte-Neo cannot verify

- Counterparty/exchange default; margin calls from intraday spikes

## Worst scenario (hedged is not risk-free)

- **This strategy:** the shorted high-funding coins rally hardest in a mania (short squeeze) while funding keeps the long side paying
- the carry flips sign (funding, curve or rate) when it is most crowded
- the hedge leg's margin is called in a fast move
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
