# Trend basket: volatility-scaled time-series momentum, 18 coins: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: trend_basket. Fixed parameters (chosen before any data was read): `{"lookback": 90, "vol_window": 30, "horizon": 7}`. Costs: Binance taker fees (VIP0: spot 10 bps, perpetual 5 bps) + 2-12 bps spread/slippage per coin, fills on the next bar; also doubled.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-10-e3c4f761`; planned Lab-wide trials: 83.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | NEEDS_MORE_EVIDENCE | 4/9 | n/a | n/a | 3 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 83 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`7e7fe9d903d1a483`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0203 (t=1.4): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 19; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | warn | bucket returns are not monotone (50% adjacent increases, rank corr 0.80): profit may sit in one extreme |
| `long_short_legs` | pass | short leg earns 47% of the spread; long leg 53% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.093/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.0155%/period; selection effect 1.0520%; with dates shuffled 0.3026% (a time-invariant tilt or market timing, not stock selection) |
| `market_impact` | pass | at AUM 5e+04: gross 57.84%, impact 15.55%, net 41.00% per year |
| `participation_limit` | pass | participation p95 0.60%, max 13.92% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 5.18e+05 and reaches zero at 1.18e+06 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 33% of short exposure in the least liquid 20%; borrow 2.90%/yr vs short-leg profit -55.03%/yr |
| `turnover_vs_decay` | info | holding 10.7 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min -7.61%, median 14.47%, max 39.72% (k=21) |
| `factor_exposure` | info | factors explain 27% of return variance; strongest: low_vol (beta -0.31, t -7.3), reversal (beta -0.19, t -6.5) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 3.2 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.38 -> 1.70 (+0.32) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.5) |
| `market_timing_beta` | info | up beta -0.00, down beta -0.01 (timing t 0.2) |
| `crowding` | info | correlation with momentum +0.28, low_vol -0.27; mean return on momentum crash days -0.0200 |
| `known_anomaly_match` | info | closest known factor: momentum (corr +0.28) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | warn | t = 2.09 is above 2 but below the Harvey-Liu-Zhu hurdle of 3.0 |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 18.5 years needed to separate Sharpe 0.69 from the best of 83 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 78.0% vs 57.4%..97.1% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.69 becomes 0.00 after Bonferroni for 83 trials (haircut 100%) |
| `neutrality` | pass | mean rolling beta -0.05, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 6.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.89 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Covid (-7.2% vs market -48.0%) |
| `tail_risk` | info | VaR95 -5.15%, CVaR95 -8.16%, CVaR99 -13.15%, worst bar -33.73%, longest recovery 443 bars |
| `universe_subsampling` | warn | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.51); top-5 symbols give 151% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 38.58% to 54.71% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.04, median 0.66, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.69 vs 0.12 median on 100 synthetic markets (p = 0.050) |
| `noise_injection` | pass | net Sharpe 0.69 -> 0.6997 at 0.1x, 0.6696 at 0.25x, 0.6389 at 0.5x |
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
| 1.39 | 1.38 | 11.25 | -0.57 | 0.65 | 0.42 | 2.32 | 0.62 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 3.87 | 0.49 | 2.20 |
| 2018 | -0.57 | -0.21 | -0.73 |
| 2019 | 0.96 | 0.38 | 0.94 |
| 2020 | 0.45 | 0.05 | 3.02 |
| 2021 | 2.54 | 5.75 | 0.60 |
| 2022 | -1.50 | -0.26 | -0.64 |
| 2023 | 0.99 | 0.31 | 1.56 |
| 2024 | 1.44 | 0.85 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
