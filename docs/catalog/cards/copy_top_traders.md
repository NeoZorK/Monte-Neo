# Copying top leaderboard traders

> Not investment advice. Research and education only; past or hypothetical results do not guarantee future results.

- **id:** `copy_top_traders`
- **type:** [Negative controls and null strategies](../TYPES.md#controls)
- **data tier:** C (A = daily OHLCV, open data; B = other data needed; C = intraday/tick)
- **source:** Exchange copy-trading products; Apesteguia Oechssler Weidenholzer 2020 Management Science
- **verification (2026-11-08):** unverified

## Definition (frozen, from the source)

Each week copy the 5 traders with the highest 30-day return on a public leaderboard

Parameters (do not tune):

- `top` = 5
- `lookback_days` = 30

**Data needed:** leaderboard history with delisted traders

**Expected regime behaviour:** CONTROL: selection on past luck; expected to fail out of sample

## Known traps

- **Survivorship bias** - Universe contains only assets that survived to today; delisted losers are missing. Monte-Neo: PLAN:universe_pit (needs point-in-time membership list).
- **Data snooping / multiple testing** - Many variants tried; the best one looks significant by chance. Monte-Neo: dsr, pbo (existing); n_trials = catalog size.
- **Small sample / few independent bets** - Too few trades or independent observations for a significance claim. Monte-Neo: trade-count gate, dsr (existing).
- **Risk of ruin** - Position sizing can lose the whole account (martingale, averaging down). Monte-Neo: PLAN:ruin_probability.

## How to measure

Metrics: Verdict distribution, false-positive rate of the verifier.
Benchmark: Verifier expectation (should not PASS).
Horizon: Same as the catalog.

## What Monte-Neo cannot verify

- Nothing special; they exist to measure verifier calibration
