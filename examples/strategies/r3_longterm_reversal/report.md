# Long-term reversal: fade the 180-day loser/winner skipping the last month (BTC-hedged): automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: cross_section. Fixed parameters (chosen before any data was read): `{"lookback": 180, "skip": 30, "horizon": 14}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-19-23bea9f6`; planned Lab-wide trials: 98.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 3 |
| validation | pre | REJECT | 2/9 | n/a | n/a | 98 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`1c3f90ade39aa141`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0042 (t=0.2): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 13; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | warn | bucket returns are not monotone (50% adjacent increases, rank corr -0.10): profit may sit in one extreme |
| `long_short_legs` | info | the top-minus-bottom spread is not positive; no profit to split |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | fail | **FAILED.**  real spread Sharpe -0.018/period is not above permuted-score placebos (p=0.776): the spread does not earn |
| `selection_vs_timing` | info | spread -0.2535%/period; selection effect -0.3508%; with dates shuffled -0.6536% (a time-invariant tilt or market timing, not stock selection) |
| `market_impact` | fail | **FAILED.**  at AUM 5e+04: gross 9.71%, impact 10.22%, net -1.29% per year |
| `participation_limit` | pass | participation p95 0.60%, max 20.44% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 10% of short exposure in the least liquid 20%; borrow 2.77%/yr vs short-leg profit -60.36%/yr |
| `turnover_vs_decay` | info | holding 16.5 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min -7.71%, median 4.26%, max 16.76% (k=21) |
| `factor_exposure` | info | factors explain 48% of return variance; strongest: momentum (beta -0.66, t -21.8), size (beta +0.04, t +1.7) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? no significant residual alpha (t 0.5) |
| `factor_spanning` | warn | adds nothing the factors do not have (max Sharpe 1.38 -> 1.39) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.6) |
| `market_timing_beta` | info | up beta 0.05, down beta -0.03 (timing t 1.2) |
| `crowding` | info | correlation with momentum -0.69, low_vol +0.08; mean return on momentum crash days +0.0529 |
| `known_anomaly_match` | info | closest known factor: momentum (corr -0.69) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 0.44, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 533.7 years needed to separate Sharpe 0.13 from the best of 98 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 87.6% vs 66.2%..99.6% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.13 becomes 0.00 after Bonferroni for 98 trials (haircut 100%) |
| `neutrality` | pass | mean rolling beta -0.02, mean net exposure -0.09 |
| `concentration` | warn | median effective positions 6.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.75 (max 2.00), net -0.09; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: FTX (-19.4% vs market -31.4%) |
| `tail_risk` | info | VaR95 -4.56%, CVaR95 -7.23%, CVaR99 -11.53%, worst bar -20.63%, longest recovery 2094 bars |
| `universe_subsampling` | warn | 91% of 100 random 70% subsets earn a positive net return (median Sharpe 0.17); top-5 symbols give 554% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | warn | annual return over 13 start dates ranges -1.28% to 9.46%: a later start loses while the full sample wins |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.18, median 0.22, 67% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.13 vs -0.29 median on 100 synthetic markets (p = 0.119): not distinguishable from the market-only null |
| `noise_injection` | pass | net Sharpe 0.13 -> 0.0974 at 0.1x, 0.2569 at 0.25x, 0.2378 at 0.5x |
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
| 0.79 | 0.75 | 1.20 | -0.22 | 0.10 | 0.01 | 1.44 | 0.13 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | 0.07 | -0.01 | -0.73 |
| 2019 | 0.26 | 0.03 | 0.94 |
| 2020 | -0.12 | -0.06 | 3.02 |
| 2021 | 0.61 | 0.21 | 0.60 |
| 2022 | 1.22 | 0.21 | -0.64 |
| 2023 | 1.51 | 0.28 | 1.56 |
| 2024 | 0.81 | 0.17 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
