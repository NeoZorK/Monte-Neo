# Pairs: ETH vs BTC log-price spread (perpetuals)

**Idea author:** Claude Sonnet 5.5. **Process, design and verification:** Rostyslav Shcherbyna.

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Regress log ETH on log BTC over a rolling 90-day window; trade the residual spread: short the spread when its z-score is above 2, long when below -2, close at |z| below 0.5. Both legs are perpetual futures (so shorting is possible) with funding charged.

## Why it might work

Two large, correlated assets can share a common driver, so their spread may mean-revert. This is statistical arbitrage in its simplest form. It is hedged against the market direction by construction.

## Where it breaks

The relationship breaks (no cointegration, regime shifts), the hedge ratio drifts, funding turns against one leg, and the P&L can be mis-booked (phantom profit): the verifier re-derives the P&L from the leg quantities (`--legs`) and runs the strategy on independent random walks, where it must not earn (`--null-test`). Cointegration tests belong to the separate pairs-checks work and will be plugged in when released.

## Fixed before looking at data

window 90, entry 2.0, exit 0.5 (grid: window 60/90/120 by entry 1.5/2/2.5). Costs: 10 bps commission + 5 bps slippage per side; fills on the next bar. The grid is used only to check that neighbouring parameters behave similarly, and every grid point counts as a trial in the deflated Sharpe.

## How it is tested

Data are split into discovery (2017-08 to 2020), validation (2021 to 2024) and a sealed holdout (2025 on). The holdout is opened once, for the candidate frozen in a git commit, through the Monte-Neo oracle and ledger. A failure is published as a reviewed case: nothing is tuned after the fact. See `report.md` (written by `scripts/strategy_lab/analyze.py`).
