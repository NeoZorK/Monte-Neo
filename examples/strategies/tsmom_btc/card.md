# Time-series momentum, BTC

**Idea author:** Claude Sonnet 5.5. **Process, design and verification:** Rostyslav Shcherbyna.

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Hold BTC while its return over the last 90 daily closes is positive; otherwise stay in cash. Long/flat, one position, daily bars.

## Why it might work

Trends in assets with slow-moving flows and herding persist (Moskowitz, Ooi, Pedersen 2012). BTC has had long persistent trends and few participants who systematically fade them.

## Where it breaks

Range-bound years with sharp reversals (whipsaw), and any regime where 90-day trends stop persisting. Costs matter when the sign flips often. One asset and about 8 years mean few independent trends, so statistical power is low.

## Fixed before looking at data

lookback 90 days (grid for the plateau check: 60, 90, 120, 180). Costs: 10 bps commission + 5 bps slippage per side; fills on the next bar. The grid is used only to check that neighbouring parameters behave similarly, and every grid point counts as a trial in the deflated Sharpe.

## How it is tested

Data are split into discovery (2017-08 to 2020), validation (2021 to 2024) and a sealed holdout (2025 on). The holdout is opened once, for the candidate frozen in a git commit, through the Monte-Neo oracle and ledger. A failure is published as a reviewed case: nothing is tuned after the fact. See `report.md` (written by `scripts/strategy_lab/analyze.py`).
