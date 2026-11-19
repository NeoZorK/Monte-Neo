# Search candidate f8e6f47c (comp_ML)

**Idea source:** systematic signal grammar (`_common/signals.py`), screened on discovery only (2017-08..2020); pre-registered in `strategy_lab/batches/batch2.json` before validation was read. **Process and verification:** Rostyslav Shcherbyna.

> Not investment advice. A research example for testing a verification pipeline, not a call to trade or a promise of profit. Simulated results do not predict future returns.

## The idea
Family `comp_ML`, parameters `{"parts": ["M", "L"]}`, sign +1; long the top third / short the bottom third of the 30 most liquid coins (point in time), rebalanced every 7 days, hedged to BTC beta.

## Why it might work
It was selected by discovery results, not by theory: net Sharpe A/B halves 1.43/1.31, costs x2 1.24, alpha t vs BTC 2.43. That is exactly why the validation count N includes every promoted candidate and a family test is run.

## Where it breaks
Selection bias from the screening; delisted coins are included only where data exist; short legs need perpetuals (funding not modelled); capacity depends on the liquid set.

## How it is tested
Validation 2021-2024 with n_trials = all Lab candidates of all rounds; holdout 2025+ sealed. See `report.md`.
