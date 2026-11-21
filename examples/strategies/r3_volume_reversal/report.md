# High-volume reversal: fade the 5-day move, stronger when volume is unusual (BTC-hedged): automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: mean_reversion. Fixed parameters (chosen before any data was read): `{"lookback": 5, "volume_window": 60, "horizon": 5}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-21-e91add2e`; planned Lab-wide trials: 98.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 3 |
| validation | pre | REJECT | 2/9 | n/a | n/a | 98 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`393942c3dce115e5`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0049 (t=0.5): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 1; IC half-life 1.1 bars |
| `quantile_monotonicity` | warn | bucket returns are not monotone (0% adjacent increases, rank corr -1.00): profit may sit in one extreme |
| `long_short_legs` | info | the top-minus-bottom spread is not positive; no profit to split |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | fail | **FAILED.**  real spread Sharpe -0.096/period is not above permuted-score placebos (p=1.000): the spread does not earn |
| `selection_vs_timing` | info | spread -0.8832%/period; selection effect -0.8968%; with dates shuffled -0.0244% (a time-invariant tilt or market timing, not stock selection) |
| `market_impact` | fail | **FAILED.**  at AUM 5e+04: gross -70.51%, impact 78.36%, net -153.92% per year |
| `participation_limit` | pass | participation p95 0.83%, max 39.25% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 19% of short exposure in the least liquid 20%; borrow 2.93%/yr vs short-leg profit -114.28%/yr |
| `turnover_vs_decay` | info | holding 2.7 bars, signal half-life 1.1 bars: you hold 2.5x longer than the signal lasts |
| `rebalance_timing_luck` | warn | annual net return by rebalance day: min -123.12%, median -41.92%, max 4.57% (k=21) |
| `factor_exposure` | info | factors explain 60% of return variance; strongest: reversal (beta +0.61, t +16.1), size (beta -0.27, t -4.4) |
| `residual_alpha` | fail | **FAILED.** Is the return still there after market, size, momentum, reversal and low-volatility exposures? 0% of the return is explained by reversal and size: repackaged factors (alpha t 0.9) |
| `factor_spanning` | warn | adds nothing the factors do not have (max Sharpe 1.38 -> 1.41) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew -0.6) |
| `market_timing_beta` | info | up beta -0.05, down beta 0.04 (timing t -1.1) |
| `crowding` | info | correlation with momentum +0.02, low_vol +0.01; mean return on momentum crash days -0.0089 |
| `known_anomaly_match` | info | closest known factor: reversal (corr +0.70) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = -2.38, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; Sharpe -0.72 is not positive, so no length of history separates it from luck |
| `drawdown_plausibility` | pass | max drawdown 100.0% vs 99.3%..100.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe -0.72 becomes -0.00 after Bonferroni for 98 trials (haircut 100%) |
| `neutrality` | pass | mean rolling beta -0.11, mean net exposure -0.09 |
| `concentration` | warn | median effective positions 6.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.87 (max 2.00), net -0.09; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: FTX (-22.3% vs market -31.4%) |
| `tail_risk` | info | VaR95 -6.40%, CVaR95 -10.99%, CVaR99 -20.24%, worst bar -51.77%, longest recovery 2625 bars |
| `universe_subsampling` | fail | **FAILED.**  0% of 100 random 70% subsets earn a positive net return (median Sharpe -0.66); top-5 symbols give no share of the profit (there is no gross profit): the result does not hold on most subsets |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges -51.21% to -35.95% |
| `cpcv_paths` | warn | net Sharpe over 15 test combinations: min -1.21, median -0.60, 0% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe -0.72 vs -0.10 median on 100 synthetic markets (p = 0.950): not distinguishable from the market-only null |
| `noise_injection` | skip | net Sharpe -0.72 is not positive: nothing to degrade |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **REJECT**, ARL **2/9**. ARL 2/9 — blocked at 3: it earns after costs (market_impact)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| -1.10 | -1.55 | -0.73 | -0.78 | 0.01 | 0.00 | -2.22 | 0.00 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 0.96 | 0.14 | 2.20 |
| 2018 | 0.16 | -0.06 | -0.73 |
| 2019 | -2.60 | -0.51 | 0.94 |
| 2020 | -2.33 | -0.47 | 3.02 |
| 2021 | -1.00 | -0.38 | 0.60 |
| 2022 | -1.30 | -0.22 | -0.64 |
| 2023 | -1.07 | -0.18 | 1.56 |
| 2024 | -1.43 | -0.31 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
