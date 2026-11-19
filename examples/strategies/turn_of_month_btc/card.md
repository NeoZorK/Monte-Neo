# Turn-of-month seasonality, BTC

**Idea author:** Claude Sonnet 5.5. **Process, design and verification:** Rostyslav Shcherbyna.

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea

Hold BTC from the 28th of each month through the 3rd of the next; cash otherwise.

## Why it might work

Calendar flows (salaries, rebalancing, monthly inflows) have supported equities around month turns. It is a deliberately simple rule with a tiny parameter space.

## Where it breaks

Crypto has no obvious salary/pension calendar; most likely a data-mining artefact. It is included to show how the verifier treats a pattern with a plausible story and weak evidence.

## Fixed before looking at data

days 28 to 3 (grid: first 27/28/29 by last 2/3/4). Costs: 10 bps commission + 5 bps slippage per side; fills on the next bar. The grid is used only to check that neighbouring parameters behave similarly, and every grid point counts as a trial in the deflated Sharpe.

## How it is tested

Data are split into discovery (2017-08 to 2020), validation (2021 to 2024) and a sealed holdout (2025 on). The holdout is opened once, for the candidate frozen in a git commit, through the Monte-Neo oracle and ledger. A failure is published as a reviewed case: nothing is tuned after the fact. See `report.md` (written by `scripts/strategy_lab/analyze.py`).
