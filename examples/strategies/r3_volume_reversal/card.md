# High-volume reversal

**Round 3** of the Strategy Lab (pre-registered before any run).

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Score = minus the 5-day return times the ratio of 5-day to 60-day dollar volume, BTC-hedged, 5-day rebalancing.

## Why it might work

Short-term price pressure from liquidity demand reverses; the volume scale tells how unusual the demand was (Llorente et al.; Campbell, Grossman and Wang).

## Where it breaks

The sign of the volume interaction is an a-priori choice and may be wrong; turnover is high so costs dominate (see cost x2). Survivorship: the 18 coins are today's liquid survivors, which flatters history (the verifier warns about it); coins that died in 2018-2022 are not in the table.

## Fixed before looking at data

lookback 5, volume window 60, horizon 5 days (grid: lookback 3/5/10). Costs (round 2): Binance taker fees by tier (default VIP0: spot 10 bps, perpetual 5 bps) plus 2-12 bps spread/slippage per coin (BTC 2, ETH 3, small coins up to 12), see `_common/binance_costs.py`; every result is also reported with costs doubled. The grid checks only the plateau and every grid point counts as a trial; `n_trials` of the certificates is the number of variants declared anywhere in the Lab.

## How it is tested

Discovery 2017-08 to 2020, validation 2021 to 2024 (bull, bear and recovery), sealed holdout 2025 on (see `strategy_lab/README.md`). The holdout is opened once, only for a candidate frozen in a git commit. A failure is published as a reviewed case; nothing is tuned afterwards. Per-regime (calendar-year) results, the share of return explained by BTC and the cost-doubling Sharpe are in `report.md`.
