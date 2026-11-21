# Cross-sectional momentum, 10 USDT spot coins


> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Rank 10 large coins by their return over the last 60 days (skipping the latest day); the score is checked by `monte-neo alpha` over a 7-day horizon (long the top, short the bottom quantiles).

## Why it might work

Winners keep winning relative to losers in the short and medium term (Jegadeesh-Titman style). A cross-section removes most of the market direction.

## Where it breaks

Survivorship: the universe is today's large coins, which flatters history (the verifier warns about it). Short legs on spot are not tradable without borrow or perpetuals. Strong coin-specific crashes and rotations.

## Fixed before looking at data

lookback 60, skip 1, horizon 7 days (grid: lookback 30/60/90). Costs: 10 bps commission + 5 bps slippage per side; fills on the next bar. The grid is used only to check that neighbouring parameters behave similarly, and every grid point counts as a trial in the deflated Sharpe.

## How it is tested

Data are split into discovery (2017-08 to 2020), validation (2021 to 2024) and a sealed holdout (2025 on). The holdout is opened once, for the candidate frozen in a git commit, through the Monte-Neo oracle and ledger. A failure is published as a reviewed case: nothing is tuned after the fact. See `report.md` (written by `scripts/strategy_lab/analyze.py`).
