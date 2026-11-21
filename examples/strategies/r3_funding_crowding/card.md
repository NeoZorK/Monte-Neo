# Funding crowding (directional)

**Round 3** of the Strategy Lab (pre-registered before any run).

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Score = minus the trailing 14-day mean daily funding rate of the coin's perpetual: short crowded longs, long the unloved, 12 coins, BTC-hedged. This is a directional cross-sectional signal; a delta-neutral spot/perp carry cannot reach ARL 6 by construction (return series only: see r2_carry_basket_v2).

## Why it might work

High funding marks crowded leverage; unwinds hurt the crowded side.

## Where it breaks

Funding is persistently positive in bull markets for all coins, the ranking may only reflect beta; funding paid or received on the perpetual legs is not included in the economics table. Survivorship: the 18 coins are today's liquid survivors, which flatters history (the verifier warns about it); coins that died in 2018-2022 are not in the table.

## Fixed before looking at data

lookback 14, horizon 7 days (grid: 7/14/30). Costs (round 2): Binance taker fees by tier (default VIP0: spot 10 bps, perpetual 5 bps) plus 2-12 bps spread/slippage per coin (BTC 2, ETH 3, small coins up to 12), see `_common/binance_costs.py`; every result is also reported with costs doubled. The grid checks only the plateau and every grid point counts as a trial; `n_trials` of the certificates is the number of variants declared anywhere in the Lab.

## How it is tested

Discovery 2017-08 to 2020, validation 2021 to 2024 (bull, bear and recovery), sealed holdout 2025 on (see `strategy_lab/README.md`). The holdout is opened once, only for a candidate frozen in a git commit. A failure is published as a reviewed case; nothing is tuned afterwards. Per-regime (calendar-year) results, the share of return explained by BTC and the cost-doubling Sharpe are in `report.md`.
