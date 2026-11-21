# VIX term-structure timing

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `vix_term_timing`
- **type:** [Long volatility and tail hedging](../TYPES.md#long_volatility)
- **data tier:** B (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Simon Campasano 2014 J. Derivatives "The VIX futures basis"
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Short the front VIX future when it trades above spot VIX by more than 0.1 per day to expiry (contango), long when below (backwardation), hedged with index futures

Parameters (do not tune):

- `threshold_per_day` = 0.1

**Data needed:** VIX spot and futures, index futures

**Expected regime behaviour:** the short side dominates; a spike reverses it in a day

## Known traps

- **Short-volatility tail / negative skew** - Steady small gains with rare large losses; Sharpe ratio and short samples hide the tail. Monte-Neo: PLAN:tail_skew_profile (skew, CVaR, worst-k, stress replay).
- **Futures roll yield** - Continuous contract built by naive stitching hides roll cost or gain. Monte-Neo: PLAN:roll_audit.
- **Crash / momentum-crash risk** - Large drawdown clustered in market rebounds or crises. Monte-Neo: PLAN:tail_skew_profile.
- **Small sample / few independent bets** - Too few trades or independent observations for a significance claim. Monte-Neo: trade-count gate, dsr (existing).
- **Regime dependence** - Works only in one market regime (e.g. a bull market) in the sample. Monte-Neo: PLAN:regime_split (sub-period / regime stability).

## How to measure

Metrics: Cost of carry per year, payoff in stress windows, effect on the portfolio's drawdown and CAGR, convexity.
Benchmark: The portfolio without the hedge; a cash-equivalent reduction of exposure.
Horizon: Must include several crashes; judged on the portfolio, not alone.

## What Monte-Neo cannot verify

- Crashes larger than any in the sample; option liquidity in the crash itself

## Worst scenario (hedged is not risk-free)

- **This strategy:** a volatility spike while short VIX futures (February 2018)
- Counterparty: a hedge does not protect the capital held at a venue that fails.

Measure it on the strategy's net returns and legs: `monte-neo catalog worst --returns r.csv --legs legs.csv` (measured losses, leg correlation in stress, and stated shocks with their formulas).
