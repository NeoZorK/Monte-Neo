# SMA trend filter, ETH

**Idea author:** Claude Sonnet 5.5. **Process, design and verification:** Rostyslav Shcherbyna.

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Hold ETH while the close is above its 100-day simple moving average; otherwise cash.

## Why it might work

The same trend-persistence argument as time-series momentum, with a smoother signal that flips less often.

## Where it breaks

Choppy sideways markets; sudden gaps down that the average reacts to late; ETH-specific events (merge, ETF news) that are not repeatable.

## Fixed before looking at data

window 100 days (grid: 50, 100, 150, 200). Costs: 10 bps commission + 5 bps slippage per side; fills on the next bar. The grid is used only to check that neighbouring parameters behave similarly, and every grid point counts as a trial in the deflated Sharpe.

## How it is tested

Data are split into discovery (2017-08 to 2020), validation (2021 to 2024) and a sealed holdout (2025 on). The holdout is opened once, for the candidate frozen in a git commit, through the Monte-Neo oracle and ledger. A failure is published as a reviewed case: nothing is tuned after the fact. See `report.md` (written by `scripts/strategy_lab/analyze.py`).
