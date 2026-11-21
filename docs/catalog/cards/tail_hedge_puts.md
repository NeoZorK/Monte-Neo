# Rolling out-of-the-money put hedge

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `tail_hedge_puts`
- **type:** [Long volatility and tail hedging](../TYPES.md#long_volatility)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Israelov 2017 FAJ "Pathetic protection"; Bhansali 2014
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Hold 1-month puts 10% out of the money on the equity index sized to 1% of portfolio value per month, rolled monthly

Parameters (do not tune):

- `moneyness` = 0.9
- `budget` = 0.01
- `roll` = monthly

**Data needed:** index option quotes, the portfolio

**Expected regime behaviour:** pays in crashes, costs every calm month

## Known traps

- **Futures roll yield** - Continuous contract built by naive stitching hides roll cost or gain. Monte-Neo: PLAN:roll_audit.
- **Small sample / few independent bets** - Too few trades or independent observations for a significance claim. Monte-Neo: trade-count gate, dsr (existing).
- **Costs** - Edge disappears under realistic transaction costs, spread, borrow and funding. Monte-Neo: cost_margin, costs_modeled (existing).
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Cost of carry per year, payoff in stress windows, effect on the portfolio's drawdown and CAGR, convexity.
Benchmark: The portfolio without the hedge; a cash-equivalent reduction of exposure.
Horizon: Must include several crashes; judged on the portfolio, not alone.

## What Monte-Neo cannot verify

- Crashes larger than any in the sample; option liquidity in the crash itself

## Worst scenario (hedged is not risk-free)

- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
