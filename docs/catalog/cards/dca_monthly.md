# Monthly dollar-cost averaging

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `dca_monthly`
- **type:** [Dollar-cost averaging and value averaging](../TYPES.md#dca)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Constantinides 1979 (critique); common retail practice
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Invest a fixed amount on the first trading day of each month

Parameters (do not tune):

- `period` = monthly

**Data needed:** price series

**Expected regime behaviour:** compare IRR with lump sum

## Known traps

- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.

## How to measure

Metrics: Money-weighted return (IRR), terminal wealth vs lump sum, regret, drawdown of invested capital.
Benchmark: Lump-sum investment at the first date; cash-held share.
Horizon: Multi-year contribution schedule.

## What Monte-Neo cannot verify

- Investor cash flows in reality; behavioural effects
