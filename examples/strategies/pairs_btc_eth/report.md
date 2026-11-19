# Pairs: ETH vs BTC log-price spread (perpetuals): automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: pairs. Fixed parameters (chosen before any data was read): `{"window": 90, "entry": 2.0, "exit": 0.5}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-3-dac23fe4`; planned Lab-wide trials: 83.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | NEEDS_MORE_EVIDENCE | 1/9 | 0.58 | 0.17 | 9 |
| validation | pre | NEEDS_MORE_EVIDENCE | 1/9 | 0.07 | 0.01 | 83 |
| holdout | not run | | | | | |

Discovery grid (Sharpe by variant; every variant is counted as a trial):

- `{'window': 60, 'entry': 1.5}` -> 0.014
- `{'window': 60, 'entry': 2.0}` -> 0.534
- `{'window': 60, 'entry': 2.5}` -> 0.237
- `{'window': 90, 'entry': 1.5}` -> 1.035
- `{'window': 90, 'entry': 2.0}` -> 0.582
- `{'window': 90, 'entry': 2.5}` -> 0.911
- `{'window': 120, 'entry': 1.5}` -> -0.654
- `{'window': 120, 'entry': 2.0}` -> 0.123
- `{'window': 120, 'entry': 2.5}` -> 0.123

## Checks of the validation certificate (`5038a198f2e45e6b`, pre data)

| Check | Status | What it means |
|---|---|---|
| `returns_only_scope` | info | Return series only: smoothing, distribution and significance were checked; look-ahead, costs and data quality behind the returns cannot be checked without the strategy or positions. |
| `data_integrity` | pass | The price table is clean (no NaN, inverted bars or duplicates). A broken table makes every other number meaningless. series is clean: finite, ordered, unique dates, no gaps, no frozen values |
| `idle_share` | info | 71% of periods have an exactly zero return (flat or out of the market); zero_kink and round_numbers run on the periods in the market only |
| `return_smoothing` | pass | no sign of smoothing (lag-1 autocorrelation -0.23, unsmoothed Sharpe 0.06) |
| `zero_kink` | pass | Return-series check. A strategy that is flat most days has many exact-zero days and few small losses; for pairs and carry this warning is expected and is not a sign of manual editing. no kink at zero (127 small losses, 90 small gains, z=2.5) |
| `implausible_consistency` | pass | 13% positive periods vs 50% expected (z=-32.0) |
| `round_numbers` | warn | Return-series check. Exactly-zero days (flat periods) count as round numbers; expected for sparse strategies, not evidence of hand-typed figures. 4% of returns are exact multiples of 5 bps vs 0.0% expected: figures may be typed or rounded by hand |
| `track_record_significance` | fail | **FAILED.** Is the track record long enough, given its Sharpe and the number of trials, to be told apart from luck? track record is not significant: probabilistic Sharpe 0.56, deflated for 83 strategies 0.01; track record 5.0 years, 510.4 needed |
| `drawdown_consistency` | pass | max drawdown 33.7% within the simulated range (5th percentile 21.3%) |

Verdict **NEEDS_MORE_EVIDENCE**, ARL **1/9**. ARL 1/9 — not assessed beyond 1: the backtest is not broken (lookahead_truncation (not run), universe_lookahead (not run))

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.00 | n/a | -0.07 | -0.34 | -0.08 | 0.01 | 0.14 | 0.01 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2020 | 0.58 | 0.06 | 3.02 |
| 2021 | -0.29 | -0.14 | 0.60 |
| 2022 | -0.37 | -0.05 | -0.64 |
| 2023 | 0.22 | 0.01 | 1.56 |
| 2024 | 0.87 | 0.13 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

Reasons given by the verifier:
- round_numbers: 4% of returns are exact multiples of 5 bps vs 0.0% expected: figures may be typed or rounded by hand
- track_record_significance: track record is not significant: probabilistic Sharpe 0.56, deflated for 83 strategies 0.01; track record 5.0 years, 510.4 needed

### Legs re-derivation (--legs): PASS_WITH_WARNINGS

- legs_scope [info]: Accounting only: the reported P&L was re-derived from the leg positions you gave. Look-ahead in the signal, trading costs and data quality are not checked here; use the full verify for them.
- data_integrity [pass]: series is clean: finite, ordered, unique dates, no gaps, no frozen values
- accounting_mismatch [pass]: the reported P&L matches the legs within 5% (unexplained 0.0%).
- derived_significance [warn]: the legs earn Sharpe +0.15 (t-statistic +0.32, 1735 bars): not distinguishable from zero.

### Random-walk null test (--null-test): PASS

- null_test_scope [info]: The strategy was run on independent random walks of your length and volatility. This finds mechanical edges (accounting, data handling); a pass does not show that the strategy has a real edge.
- edge_on_noise [pass]: no edge on noise, on 100 independent random-walk sets: median Sharpe -0.32, 22% positive, median t-statistic -0.91.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
