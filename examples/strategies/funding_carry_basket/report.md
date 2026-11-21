# Funding carry: long spot / short perpetual basket: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: carry. Fixed parameters (chosen before any data was read): `{"lookback": 7, "threshold": 0.0002}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-4-2b0dc5c2`; planned Lab-wide trials: 83.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 1/9 | 6.66 | 1.00 | 9 |
| validation | pre | PASS_WITH_WARNINGS | 1/9 | 5.86 | 1.00 | 83 |
| holdout | not run | | | | | |

Discovery grid (Sharpe by variant; every variant is counted as a trial):

- `{'lookback': 3, 'threshold': 0.0001}` -> 5.835
- `{'lookback': 3, 'threshold': 0.0002}` -> 5.854
- `{'lookback': 3, 'threshold': 0.0004}` -> 5.132
- `{'lookback': 7, 'threshold': 0.0001}` -> 6.757
- `{'lookback': 7, 'threshold': 0.0002}` -> 6.672
- `{'lookback': 7, 'threshold': 0.0004}` -> 5.369
- `{'lookback': 14, 'threshold': 0.0001}` -> 7.481
- `{'lookback': 14, 'threshold': 0.0002}` -> 7.199
- `{'lookback': 14, 'threshold': 0.0004}` -> 6.256

## Checks of the validation certificate (`b6ab82f442412676`, pre data)

| Check | Status | What it means |
|---|---|---|
| `returns_only_scope` | info | Return series only: smoothing, distribution and significance were checked; look-ahead, costs and data quality behind the returns cannot be checked without the strategy or positions. |
| `data_integrity` | pass | The price table is clean (no NaN, inverted bars or duplicates). A broken table makes every other number meaningless. series is clean: finite, ordered, unique dates, no gaps, no frozen values |
| `idle_share` | info | 27% of periods have an exactly zero return (flat or out of the market); zero_kink and round_numbers run on the periods in the market only |
| `return_smoothing` | warn | returns look smoothed (lag-1 autocorrelation 0.48, t=20.7): illiquid marks or stale pricing; the unsmoothed Sharpe is 3.50 (reported 5.86) |
| `zero_kink` | warn | Return-series check. A strategy that is flat most days has many exact-zero days and few small losses; for pairs and carry this warning is expected and is not a sign of manual editing. small losses are missing: 143 small losses vs 358 small gains (expected about 239.2 losses, z=-8.6); losses may be deferred or rounded up |
| `implausible_consistency` | pass | 53% positive periods vs 62% expected (z=-7.9) |
| `round_numbers` | warn | Return-series check. Exactly-zero days (flat periods) count as round numbers; expected for sparse strategies, not evidence of hand-typed figures. 2% of returns are exact multiples of 5 bps vs 0.0% expected: figures may be typed or rounded by hand |
| `track_record_significance` | pass | Is the track record long enough, given its Sharpe and the number of trials, to be told apart from luck? probabilistic Sharpe 1.00, deflated for 83 strategies 1.00; track record 5.0 years, 0.1 needed |
| `drawdown_consistency` | pass | max drawdown 3.4% within the simulated range (5th percentile 0.5%) |

Verdict **PASS_WITH_WARNINGS**, ARL **1/9**. ARL 1/9 — not assessed beyond 1: the backtest is not broken (lookahead_truncation (not run), universe_lookahead (not run))

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 5.69 | n/a | 0.32 | -0.03 | -0.02 | 0.00 | 11.42 | 1.00 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2020 | 6.66 | 0.12 | 3.02 |
| 2021 | 11.90 | 0.27 | 0.60 |
| 2022 | -4.56 | -0.02 | -0.64 |
| 2023 | 0.54 | 0.00 | 1.56 |
| 2024 | 8.07 | 0.06 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

Reasons given by the verifier:
- return_smoothing: returns look smoothed (lag-1 autocorrelation 0.48, t=20.7): illiquid marks or stale pricing; the unsmoothed Sharpe is 3.50 (reported 5.86)
- zero_kink: small losses are missing: 143 small losses vs 358 small gains (expected about 239.2 losses, z=-8.6); losses may be deferred or rounded up
- round_numbers: 2% of returns are exact multiples of 5 bps vs 0.0% expected: figures may be typed or rounded by hand

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
