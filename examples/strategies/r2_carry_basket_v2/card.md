# Funding carry v2: long spot / short perpetual, 12 coins, per-coin costs

**Round 2** of the Strategy Lab (pre-registered before any run).

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Hold spot long and perpetual short in a coin while its trailing 14-day mean daily funding exceeds 0.02 % per day; equal weight; return on capital including 25 % margin.

## Why it might work

Longs pay shorts when perpetuals trade above spot; the position is delta-neutral, so most of the return is funding.

## Where it breaks

Funding flips sign, basis moves hurt the legs before they converge, exchange and liquidation risk on the short leg. Note: it is a returns-only series, so the verifier cannot test timing or placebo on a signal; the Lab adds data integrity checks on the input prices and labels the ARL as capped. Survivorship: the 18 coins are today's liquid survivors, which flatters history (the verifier warns about it); coins that died in 2018-2022 are not in the table.

## Fixed before looking at data

lookback 14, threshold 0.0002 per day (grid: lookback 7/14/30). Costs (round 2): Binance taker fees by tier (default VIP0: spot 10 bps, perpetual 5 bps) plus 2-12 bps spread/slippage per coin (BTC 2, ETH 3, small coins up to 12), see `_common/binance_costs.py`; every result is also reported with costs doubled. The grid checks only the plateau and every grid point counts as a trial; `n_trials` of the certificates is the number of variants declared anywhere in the Lab.

## How it is tested

Discovery 2017-08 to 2020, validation 2021 to 2024 (bull, bear and recovery), sealed holdout 2025 on (see `strategy_lab/README.md`). The holdout is opened once, only for a candidate frozen in a git commit. A failure is published as a reviewed case; nothing is tuned afterwards. Per-regime (calendar-year) results, the share of return explained by BTC and the cost-doubling Sharpe are in `report.md`.
