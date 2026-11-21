# Bollinger band reversion, ETH


> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Buy when the close is more than 2 standard deviations below the 20-day mean; hold until the close returns to the mean.

## Why it might work

Prices that stretch far from a short-term average often snap back. A classical, widely known rule fixed before looking at ETH data.

## Where it breaks

Persistent downtrends (it keeps buying falling prices); volatility regime changes that make 2 sigma a poor threshold; likely weak after costs.

## Fixed before looking at data

window 20, k 2.0 (grid: window 20/40 by k 1.5/2/2.5). Costs: 10 bps commission + 5 bps slippage per side; fills on the next bar. The grid is used only to check that neighbouring parameters behave similarly, and every grid point counts as a trial in the deflated Sharpe.

## How it is tested

Data are split into discovery (2017-08 to 2020), validation (2021 to 2024) and a sealed holdout (2025 on). The holdout is opened once, for the candidate frozen in a git commit, through the Monte-Neo oracle and ledger. A failure is published as a reviewed case: nothing is tuned after the fact. See `report.md` (written by `scripts/strategy_lab/analyze.py`).
