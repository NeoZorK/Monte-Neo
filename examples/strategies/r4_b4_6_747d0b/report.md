# Search candidate 747d0bb3: voltrend {'lookback': 14, 'volume_window': 60} sign 1, top 30 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_voltrend. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-54-5a8d0ef9`; planned Lab-wide trials: 134.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 4/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`6be67c948be304f3`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0224 (t=2.0): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 19; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 0.90, spread 1.6797% per period) |
| `long_short_legs` | pass | short leg earns 43% of the spread; long leg 57% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.166/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.6797%/period; selection effect 1.7011%; with dates shuffled 0.2409% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | pass | net return +35.9% a year at the modelled costs, +1.1% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | pass | at AUM 5e+04: gross 102.44%, impact 47.29%, net 52.04% per year |
| `participation_limit` | pass | participation p95 1.02%, max 39.87% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 2.28e+05 and reaches zero at 2.28e+05 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 5% of short exposure in the least liquid 20%; borrow 2.93%/yr vs short-leg profit -1.15%/yr |
| `turnover_vs_decay` | info | holding 4.5 bars |
| `rebalance_timing_luck` | warn | annual net return by rebalance day: min -8.27%, median 28.36%, max 54.35% (k=21) |
| `factor_exposure` | info | factors explain 14% of return variance; strongest: reversal (beta -0.46, t -12.2), size (beta -0.13, t -2.9) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 4.8 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.34 (+0.66) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.4) |
| `market_timing_beta` | info | up beta -0.04, down beta -0.05 (timing t 0.1) |
| `crowding` | info | correlation with momentum -0.05, low_vol -0.00; mean return on momentum crash days +0.0056 |
| `known_anomaly_match` | info | closest known factor: reversal (corr -0.36) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 1.83, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 29.5 years needed to separate Sharpe 0.58 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 85.9% vs 63.3%..98.8% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.58 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.226 over 134 trial(s) on net returns (Sharpe 0.58 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.06, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 10.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.91 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: FTX (-6.5% vs market -31.4%) |
| `tail_risk` | info | VaR95 -5.45%, CVaR95 -8.41%, CVaR99 -13.98%, worst bar -22.60%, longest recovery 416 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.84); top-5 symbols give 55% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 64.61% to 84.09% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.63, median 1.08, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 1.14 vs 0.07 median on 100 synthetic markets (p = 0.020) |
| `noise_injection` | pass | net Sharpe 1.14 -> 1.1258 at 0.1x, 1.0599 at 0.25x, 0.8852 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **NEEDS_MORE_EVIDENCE**, ARL **3/9**. ARL 3/9 — blocked at 4: the signal predicts (ic)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.78 | 0.47 | 0.91 | -0.27 | 0.06 | 0.00 | 1.47 | 0.14 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | -0.13 | -0.06 | 2.20 |
| 2018 | 2.75 | 2.64 | -0.73 |
| 2019 | -0.17 | -0.06 | 0.94 |
| 2020 | 1.92 | 0.61 | 3.02 |
| 2021 | 0.65 | 0.18 | 0.60 |
| 2022 | 0.71 | 0.14 | -0.64 |
| 2023 | 1.36 | 0.24 | 1.56 |
| 2024 | 0.69 | 0.15 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
