# Donchian channel position basket, 18 coins

**Idea author:** Claude Sonnet 5.5. **Process, design and verification:** Rostyslav Shcherbyna. **Round 2** of the Strategy Lab (pre-registered before any run).

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Each coin is held long when its close is in the upper half of the channel formed by the previous 55 closes, flat otherwise.

## Why it might work

Breakout and channel rules are classic trend-following; they react to the level, not to a fitted slope.

## Where it breaks

Same market-factor dependence as any long-only trend basket; late entries after the move; many false breakouts in ranges. Survivorship: the 18 coins are today's liquid survivors, which flatters history (the verifier warns about it); coins that died in 2018-2022 are not in the table.

## Fixed before looking at data

window 55, horizon 7 days (grid: window 40/55/80). Costs (round 2): Binance taker fees by tier (default VIP0: spot 10 bps, perpetual 5 bps) plus 2-12 bps spread/slippage per coin (BTC 2, ETH 3, small coins up to 12), see `_common/binance_costs.py`; every result is also reported with costs doubled. The grid checks only the plateau and every grid point counts as a trial; `n_trials` of the certificates is the number of variants declared anywhere in the Lab.

## How it is tested

Discovery 2017-08 to 2020, validation 2021 to 2024 (bull, bear and recovery), sealed holdout 2025 on (see `strategy_lab/README.md`). The holdout is opened once, only for a candidate frozen in a git commit. A failure is published as a reviewed case; nothing is tuned afterwards. Per-regime (calendar-year) results, the share of return explained by BTC and the cost-doubling Sharpe are in `report.md`.
