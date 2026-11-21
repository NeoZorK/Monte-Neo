# RSI(2) mean reversion in an uptrend, BTC


> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Buy when the 2-day RSI is below 10 while the close is above its 200-day average; exit when RSI rises above 70.

## Why it might work

Short-term overreaction inside a longer uptrend tends to revert (Connors-style rule). Mean reversion is a different return source than trend following, so it could diversify it.

## Where it breaks

Trend-less or crashing markets where dips keep dipping; strong trending bull runs where the rule sits out; small average gain per trade eaten by costs.

## Fixed before looking at data

RSI length 2, buy below 10, sell above 70, trend filter 200 (grid: buy 5/10/15, sell 60/70). Costs: 10 bps commission + 5 bps slippage per side; fills on the next bar. The grid is used only to check that neighbouring parameters behave similarly, and every grid point counts as a trial in the deflated Sharpe.

## How it is tested

Data are split into discovery (2017-08 to 2020), validation (2021 to 2024) and a sealed holdout (2025 on). The holdout is opened once, for the candidate frozen in a git commit, through the Monte-Neo oracle and ledger. A failure is published as a reviewed case: nothing is tuned after the fact. See `report.md` (written by `scripts/strategy_lab/analyze.py`).
