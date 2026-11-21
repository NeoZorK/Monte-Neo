# Funding carry v2: long spot / short perpetual, 12 coins, per-coin costs: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: carry. Fixed parameters (chosen before any data was read): `{"lookback": 14, "threshold": 0.0002}`. Costs: Binance taker fees (VIP0: spot 10 bps, perpetual 5 bps) + 2-12 bps spread/slippage per coin, fills on the next bar; also doubled.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-5-eeba9cf5`; planned Lab-wide trials: 83.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 1/9 | 9.02 | 1.00 | 3 |
| validation | pre | PASS_WITH_WARNINGS | 1/9 | 7.16 | 1.00 | 83 |
| holdout | not run | | | | | |

Discovery grid (Sharpe by variant; every variant is counted as a trial):

- `{'lookback': 7}` -> 7.311
- `{'lookback': 14}` -> 9.031
- `{'lookback': 30}` -> 7.102

## Checks of the validation certificate (`af645961442e6673`, pre data)

| Check | Status | What it means |
|---|---|---|
| `returns_only_scope` | info | Return series only: smoothing, distribution and significance were checked; look-ahead, costs and data quality behind the returns cannot be checked without the strategy or positions. |
| `data_integrity` | pass | The price table is clean (no NaN, inverted bars or duplicates). A broken table makes every other number meaningless. series is clean: finite, ordered, unique dates, no gaps, no frozen values |
| `idle_share` | info | 15% of periods have an exactly zero return (flat or out of the market) |
| `return_smoothing` | warn | returns look smoothed (lag-1 autocorrelation 0.61, t=26.2): illiquid marks or stale pricing; the unsmoothed Sharpe is 4.21 (reported 7.16) |
| `zero_kink` | warn | Return-series check. A strategy that is flat most days has many exact-zero days and few small losses; for pairs and carry this warning is expected and is not a sign of manual editing. small losses are missing: 323 small losses vs 716 small gains (expected about 495.3 losses, z=-10.7); losses may be deferred or rounded up |
| `implausible_consistency` | pass | 58% positive periods vs 65% expected (z=-5.5) |
| `round_numbers` | warn | Return-series check. Exactly-zero days (flat periods) count as round numbers; expected for sparse strategies, not evidence of hand-typed figures. 15% of returns are exact multiples of 5 bps vs 0.0% expected: figures may be typed or rounded by hand |
| `track_record_significance` | pass | Is the track record long enough, given its Sharpe and the number of trials, to be told apart from luck? probabilistic Sharpe 1.00, deflated for 83 strategies 1.00; track record 5.0 years, 0.1 needed |
| `drawdown_consistency` | pass | max drawdown 1.1% within the simulated range (5th percentile 0.4%) |

Verdict **PASS_WITH_WARNINGS**, ARL **1/9**. ARL 1/9 — not assessed beyond 1: the backtest is not broken (lookahead_truncation (not run), universe_lookahead (not run))

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 6.67 | 5.00 | 0.44 | -0.01 | -0.02 | 0.00 | 13.38 | 1.00 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2020 | 9.02 | 0.14 | 3.02 |
| 2021 | 12.55 | 0.33 | 0.60 |
| 2022 | -2.40 | -0.01 | -0.64 |
| 2023 | 3.74 | 0.02 | 1.56 |
| 2024 | 8.91 | 0.07 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

Reasons given by the verifier:
- return_smoothing: returns look smoothed (lag-1 autocorrelation 0.61, t=26.2): illiquid marks or stale pricing; the unsmoothed Sharpe is 4.21 (reported 7.16)
- zero_kink: small losses are missing: 323 small losses vs 716 small gains (expected about 495.3 losses, z=-10.7); losses may be deferred or rounded up
- round_numbers: 15% of returns are exact multiples of 5 bps vs 0.0% expected: figures may be typed or rounded by hand

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
