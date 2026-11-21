# Search candidate ff056945: hi {'window': 30} sign 1, top 30 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_hi. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-27-acc18e6a`; planned Lab-wide trials: 104.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | NEEDS_MORE_EVIDENCE | 4/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 4/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`86ec694c5d32e80b`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0581 (t=6.0, ICIR 0.19): the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 0.8805% per period) |
| `long_short_legs` | pass | short leg earns 44% of the spread; long leg 56% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.117/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 0.7866%/period; selection effect 0.9028%; with dates shuffled 0.2725% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | warn | the edge does not survive doubled costs: net return +25.5% a year at the modelled costs, -6.3% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | warn | at AUM 5e+04: gross 83.13%, impact 43.24%, net 37.01% per year |
| `participation_limit` | pass | participation p95 0.78%, max 18.46% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 2.28e+05 and reaches zero at 2.28e+05 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 9% of short exposure in the least liquid 20%; borrow 2.94%/yr vs short-leg profit -11.46%/yr |
| `turnover_vs_decay` | info | holding 4.7 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min -3.37%, median 48.88%, max 66.99% (k=21) |
| `factor_exposure` | info | factors explain 30% of return variance; strongest: reversal (beta -0.46, t -10.4), low_vol (beta +0.36, t +6.3) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 3.9 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.18 (+0.50) |
| `hidden_short_volatility` | warn | short-option payoff signs: negative convexity to the market |
| `market_timing_beta` | info | up beta -0.40, down beta -0.25 (timing t -1.7) |
| `crowding` | info | correlation with momentum -0.09, low_vol +0.35; mean return on momentum crash days +0.0136 |
| `known_anomaly_match` | info | closest known factor: reversal (corr -0.38) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 1.33, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 61.3 years needed to separate Sharpe 0.40 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 81.7% vs 67.7%..99.6% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.40 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.092 over 134 trial(s) on net returns (Sharpe 0.40 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | warn | mean rolling beta -0.35, mean net exposure -0.09: declared neutral but is not |
| `concentration` | warn | median effective positions 12.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.87 (max 2.00), net -0.09; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Volmageddon (-39.6% vs market -0.3%) |
| `tail_risk` | info | VaR95 -5.70%, CVaR95 -9.11%, CVaR99 -14.71%, worst bar -31.19%, longest recovery 948 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.79); top-5 symbols give 60% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 57.35% to 68.73% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.17, median 0.90, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.90 vs 0.31 median on 100 synthetic markets (p = 0.040) |
| `noise_injection` | pass | net Sharpe 0.90 -> 1.0572 at 0.1x, 1.0637 at 0.25x, 1.0286 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **NEEDS_MORE_EVIDENCE**, ARL **4/9**. ARL 4/9 — blocked at 5: it is new alpha (hidden_short_volatility)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 1.06 | 0.67 | 1.62 | -0.28 | 0.07 | 0.01 | 2.02 | 0.30 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 4.21 | 1.21 | 2.20 |
| 2018 | 2.03 | 1.19 | -0.73 |
| 2019 | 1.10 | 0.21 | 0.94 |
| 2020 | 1.28 | 0.44 | 3.02 |
| 2021 | 2.31 | 0.96 | 0.60 |
| 2022 | 0.79 | 0.17 | -0.64 |
| 2023 | 0.60 | 0.11 | 1.56 |
| 2024 | 0.25 | 0.03 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
