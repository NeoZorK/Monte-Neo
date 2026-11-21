# Search candidate 1d13a6fc: comp_LHZ {'parts': ['L', 'H', 'Z']} sign 1, top 60 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_comp_LHZ. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-29-60faaf11`; planned Lab-wide trials: 114.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 4/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 4/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`6329b69c1309ee51`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0783 (t=4.8, ICIR 0.28): the signal predicts returns |
| `ic_decay` | info | best horizon 19; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 4.3277% per period) |
| `long_short_legs` | pass | short leg earns 34% of the spread; long leg 66% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.218/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 4.3277%/period; selection effect 4.2944%; with dates shuffled 0.0011% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | pass | net return +38.1% a year at the modelled costs, +28.5% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | pass | at AUM 5e+04: gross 69.12%, impact 12.95%, net 55.19% per year |
| `participation_limit` | pass | participation p95 0.26%, max 74.48% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 1.18e+06 and reaches zero at 2.68e+06 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 0% of short exposure in the least liquid 20%; borrow 2.59%/yr vs short-leg profit -23.37%/yr |
| `turnover_vs_decay` | info | holding 12.3 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 39.51%, median 50.86%, max 64.49% (k=21) |
| `factor_exposure` | info | factors explain 18% of return variance; strongest: low_vol (beta +0.30, t +4.6), market (beta -0.14, t -3.7) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 2.4 is below the Harvey-Liu-Zhu hurdle of 3.0 |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 1.92 (+0.23) |
| `hidden_short_volatility` | fail | **FAILED.**  steady gains and rare crashes: the strategy sells insurance |
| `market_timing_beta` | info | up beta -0.33, down beta -0.20 (timing t -1.5) |
| `crowding` | info | correlation with momentum +0.01, low_vol +0.33; mean return on momentum crash days +0.0036 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.33) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | warn | t = 2.17 is above 2 but below the Harvey-Liu-Zhu hurdle of 3.0 |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 18.6 years needed to separate Sharpe 0.73 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 73.0% vs 52.9%..95.5% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.73 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.403 over 134 trial(s) on net returns (Sharpe 0.73 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.27, mean net exposure -0.08 |
| `concentration` | warn | median effective positions 14.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.65 (max 2.00), net -0.08; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: SVB (-18.2% vs market 6.7%) |
| `tail_risk` | info | VaR95 -4.18%, CVaR95 -7.14%, CVaR99 -13.23%, worst bar -61.74%, longest recovery 544 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.74); top-5 symbols give 59% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 47.69% to 61.81% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.09, median 0.65, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.91 vs -0.09 median on 100 synthetic markets (p = 0.010) |
| `noise_injection` | pass | net Sharpe 0.91 -> 0.9278 at 0.1x, 0.9015 at 0.25x, 0.8497 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **NEEDS_MORE_EVIDENCE**, ARL **4/9**. ARL 4/9 — blocked at 5: it is new alpha (hidden_short_volatility, residual_alpha)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 1.25 | 1.14 | 1.64 | -0.29 | 0.00 | 0.00 | 2.49 | 0.45 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | -0.92 | -0.18 | -0.73 |
| 2019 | 3.56 | 1.34 | 0.94 |
| 2020 | 2.73 | 0.94 | 3.02 |
| 2021 | 2.73 | 1.36 | 0.60 |
| 2022 | -1.05 | -0.13 | -0.64 |
| 2023 | 1.53 | 0.21 | 1.56 |
| 2024 | 0.44 | 0.07 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
