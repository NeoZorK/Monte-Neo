# Funding carry: long spot / short perpetual basket


> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

In each of BTC, ETH, BNB, SOL, hold long spot and short the perpetual (delta-neutral) while the trailing 7-day mean daily funding rate is above 0.02%; equal weight; capital is spot notional plus 25% margin.

## Why it might work

Perpetual futures pay long holders' funding to shorts when demand for leverage is high; a delta-neutral position collects it without taking price direction. The return is a payment for supplying liquidity, not a forecast.

## Where it breaks

Funding turns negative or basis moves against the hedge in a squeeze; exchange, liquidation and counterparty risks that a return series cannot show; the capital-efficiency assumption (25% margin) is an assumption. Verified as a RETURN series: the look-ahead probes of a signal file do not apply, so the evidence ceiling is lower.

## Fixed before looking at data

lookback 7 days, threshold 0.0002 per day (grid: lookback 3/7/14 by threshold 0.0001/0.0002/0.0004). Costs: 10 bps commission + 5 bps slippage per side; fills on the next bar. The grid is used only to check that neighbouring parameters behave similarly, and every grid point counts as a trial in the deflated Sharpe.

## How it is tested

Data are split into discovery (2017-08 to 2020), validation (2021 to 2024) and a sealed holdout (2025 on). The holdout is opened once, for the candidate frozen in a git commit, through the Monte-Neo oracle and ledger. A failure is published as a reviewed case: nothing is tuned after the fact. See `report.md` (written by `scripts/strategy_lab/analyze.py`).
