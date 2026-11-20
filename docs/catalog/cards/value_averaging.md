# Value averaging

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `value_averaging`
- **type:** [Dollar-cost averaging and value averaging](../TYPES.md#dca)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Edleson 1991
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Target portfolio value path grows by fixed amount per period; trade the difference

Parameters (do not tune):

- `period` = monthly
- `target_growth` = fixed monthly increment

**Data needed:** price series

**Expected regime behaviour:** forced buy-low sell-high

## Known traps

- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).
- **Hidden market beta** - Reported return is mostly exposure to the market or a known factor, not skill. Monte-Neo: benchmark (existing, info only); PLAN:alpha_after_beta gate.

## How to measure

Metrics: Money-weighted return (IRR), terminal wealth vs lump sum, regret, drawdown of invested capital.
Benchmark: Lump-sum investment at the first date; cash-held share.
Horizon: Multi-year contribution schedule.

## What Monte-Neo cannot verify

- Investor cash flows in reality; behavioural effects
