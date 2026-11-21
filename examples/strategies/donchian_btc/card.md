# Donchian breakout 55/20, BTC


> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Enter long on a close above the previous 55-day high; exit on a close below the previous 20-day low (classic Turtle rules, long only).

## Why it might work

Breakouts capture the start of large moves and the asymmetric exit lets winners run. The rule is decades old and was not designed for crypto, which lowers the odds that it is overfitted to it.

## Where it breaks

False breakouts in ranges; few trades (dozens in 8 years), so the trade-count and significance checks are likely to be the binding ones.

## Fixed before looking at data

entry 55, exit 20 (grid: entry 20/40/55 by exit 10/20). Costs: 10 bps commission + 5 bps slippage per side; fills on the next bar. The grid is used only to check that neighbouring parameters behave similarly, and every grid point counts as a trial in the deflated Sharpe.

## How it is tested

Data are split into discovery (2017-08 to 2020), validation (2021 to 2024) and a sealed holdout (2025 on). The holdout is opened once, for the candidate frozen in a git commit, through the Monte-Neo oracle and ledger. A failure is published as a reviewed case: nothing is tuned after the fact. See `report.md` (written by `scripts/strategy_lab/analyze.py`).
