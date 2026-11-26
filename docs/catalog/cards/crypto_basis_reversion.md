# Spot-perpetual basis reversion

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `crypto_basis_reversion`
- **type:** [Carry (FX, commodity roll, bond roll-down, crypto funding/basis)](../TYPES.md#carry)
- **data tier:** A (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** He Manela Ross von Wachter 2022 'Fundamentals of perpetual futures' (arXiv 2212.06888); law of one price
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Per coin, z-score of log(perp/spot) over 60 days; above 2 buy spot and sell the perpetual in equal notional; close both below 0.5; equal capital per coin with 25% margin

Parameters (do not tune):

- `window` = 60
- `entry` = 2.0
- `exit` = 0.5
- `margin` = 0.25

**Data needed:** spot and perpetual daily closes, funding history

**Expected regime behaviour:** premia stretch in leveraged bull phases; can stay stretched for weeks

## Known traps

- **Funding rate and basis risk** - Perpetual funding changes sign; basis can widen; exchange/margin risk is not a price series. Monte-Neo: PLAN:carry_decomposition.
- **Execution timing** - Trade assumed at the close/open that generated the signal. Monte-Neo: lookahead, timing (existing).
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Stale prices / illiquid quotes** - Last trade used as executable price in thin markets. Monte-Neo: data_integrity (partly).
- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).

## How to measure

Metrics: Carry return vs spot return decomposition, Sharpe, skew, crash drawdowns, funding sign flips, margin usage.
Benchmark: Spot/buy-and-hold; cash.
Horizon: Includes a crisis (2008 FX, 2020 and 2022 crypto).

## What Monte-Neo cannot verify

- Counterparty/exchange default; margin calls from intraday spikes

## Worst scenario (hedged is not risk-free)

- **This strategy:** the premium keeps widening while the short perpetual's margin is called in a fast rally; both legs sit on one venue
- the carry flips sign (funding, curve or rate) when it is most crowded
- the hedge leg's margin is called in a fast move
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
