# BTC-neutral residual momentum, long-short, 18 coins: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: market_neutral. Fixed parameters (chosen before any data was read): `{"lookback": 60, "skip": 1, "beta_window": 90, "horizon": 7}`. Costs: Binance taker fees (VIP0: spot 10 bps, perpetual 5 bps) + 2-12 bps spread/slippage per coin, fills on the next bar; also doubled.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-9-14d084cd`; planned Lab-wide trials: 83.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 3 |
| validation | pre | PASS_WITH_WARNINGS | 3/9 | n/a | n/a | 83 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`72b59779ba514105`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0164 (t=1.1): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 14; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 1.8210% per period) |
| `long_short_legs` | pass | short leg earns 43% of the spread; long leg 57% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.146/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.8210%/period; selection effect 1.7924%; with dates shuffled 0.2682% (a time-invariant tilt or market timing, not stock selection) |
| `market_impact` | pass | at AUM 5e+04: gross 77.79%, impact 20.14%, net 56.20% per year |
| `participation_limit` | pass | participation p95 0.71%, max 26.17% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 5.18e+05 and reaches zero at 1.18e+06 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 32% of short exposure in the least liquid 20%; borrow 2.90%/yr vs short-leg profit -44.57%/yr |
| `turnover_vs_decay` | info | holding 9.3 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 27.44%, median 50.39%, max 73.17% (k=21) |
| `factor_exposure` | info | factors explain 20% of return variance; strongest: low_vol (beta -0.36, t -6.3), market (beta -0.12, t -3.4) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 4.1 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.38 -> 1.83 (+0.45) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 1.1) |
| `market_timing_beta` | info | up beta 0.02, down beta -0.06 (timing t 1.1) |
| `crowding` | info | correlation with momentum +0.19, low_vol -0.27; mean return on momentum crash days -0.0132 |
| `known_anomaly_match` | info | closest known factor: low_vol (corr -0.27) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | warn | t = 2.55 is above 2 but below the Harvey-Liu-Zhu hurdle of 3.0 |
| `min_backtest_length` | warn | How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 13.8 years needed to separate Sharpe 0.80 from the best of 83 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 86.7% vs 61.9%..98.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.80 becomes 0.10 after Bonferroni for 83 trials (haircut 87%) |
| `neutrality` | pass | mean rolling beta -0.07, mean net exposure -0.09 |
| `concentration` | warn | median effective positions 6.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.84 (max 2.00), net -0.09; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Covid (-4.2% vs market -48.0%) |
| `tail_risk` | info | VaR95 -5.94%, CVaR95 -9.34%, CVaR99 -14.78%, worst bar -21.88%, longest recovery 692 bars |
| `universe_subsampling` | warn | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.81); top-5 symbols give 99% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 53.63% to 73.14% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.21, median 0.82, 93% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.80 vs 0.11 median on 100 synthetic markets (p = 0.020) |
| `noise_injection` | pass | net Sharpe 0.80 -> 0.7552 at 0.1x, 0.6981 at 0.25x, 0.5852 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **PASS_WITH_WARNINGS**, ARL **3/9**. ARL 3/9 — blocked at 4: the signal predicts (ic)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.88 | 0.77 | 1.16 | -0.20 | 0.02 | 0.00 | 1.73 | 0.24 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 1.09 | 0.15 | 2.20 |
| 2018 | 0.01 | -0.07 | -0.73 |
| 2019 | 1.71 | 0.52 | 0.94 |
| 2020 | 1.89 | 0.54 | 3.02 |
| 2021 | 1.39 | 0.60 | 0.60 |
| 2022 | -0.07 | -0.03 | -0.64 |
| 2023 | 1.52 | 0.31 | 1.56 |
| 2024 | 0.40 | 0.06 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
