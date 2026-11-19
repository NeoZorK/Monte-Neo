# Volatility-targeted trend, BTC

**Idea author:** Claude Sonnet 5.5. **Process, design and verification:** Rostyslav Shcherbyna.

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Trend filter (close above 100-day average) with the position sized to a 40% annual volatility target (30-day realised volatility), weight capped at 1.

## Why it might work

Sizing by inverse volatility stabilises risk, shrinks exposure before and during crashes and usually improves risk-adjusted return over the plain trend rule.

## Where it breaks

Volatility spikes with no warning (the estimate lags); frequent small rebalances create turnover costs; the improvement may be mostly lower drawdown, not higher Sharpe.

## Fixed before looking at data

SMA 100, target 0.40, vol window 30 (grid: SMA 50/100/200 by target 0.3/0.4/0.5). Costs: 10 bps commission + 5 bps slippage per side; fills on the next bar. The grid is used only to check that neighbouring parameters behave similarly, and every grid point counts as a trial in the deflated Sharpe.

## How it is tested

Data are split into discovery (2017-08 to 2020), validation (2021 to 2024) and a sealed holdout (2025 on). The holdout is opened once, for the candidate frozen in a git commit, through the Monte-Neo oracle and ledger. A failure is published as a reviewed case: nothing is tuned after the fact. See `report.md` (written by `scripts/strategy_lab/analyze.py`).
