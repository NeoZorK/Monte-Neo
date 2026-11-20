# Search candidate a401cfd2: resmom {'lookback': 30, 'beta_window': 90} sign 1, top 60 liquid coins: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_resmom. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-32-57fc3c75`; planned Lab-wide trials: 114.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 3/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`a3eba181023d70ec`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC -0.0084 (t=-0.7): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 13; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 0.9865% per period) |
| `long_short_legs` | pass | short leg earns 35% of the spread; long leg 65% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.102/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 0.9865%/period; selection effect 0.9821%; with dates shuffled 0.2079% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | warn | the edge does not survive doubled costs: net return +19.2% a year at the modelled costs, -7.5% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | warn | at AUM 5e+04: gross 66.52%, impact 36.56%, net 27.79% per year |
| `participation_limit` | pass | participation p95 1.21%, max 56.01% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 2.28e+05 and reaches zero at 2.28e+05 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 5% of short exposure in the least liquid 20%; borrow 2.87%/yr vs short-leg profit -17.15%/yr |
| `turnover_vs_decay` | info | holding 6.3 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 6.36%, median 33.00%, max 47.87% (k=21) |
| `factor_exposure` | info | factors explain 17% of return variance; strongest: reversal (beta -0.31, t -7.2), size (beta -0.26, t -5.8) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 4.7 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.34 (+0.66) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.5) |
| `market_timing_beta` | info | up beta 0.01, down beta -0.09 (timing t 1.6) |
| `crowding` | info | correlation with momentum +0.03, low_vol -0.16; mean return on momentum crash days +0.0035 |
| `known_anomaly_match` | info | closest known factor: reversal (corr -0.31) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 1.13, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 71.4 years needed to separate Sharpe 0.37 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 81.6% vs 59.5%..98.8% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.37 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.076 over 134 trial(s) on net returns (Sharpe 0.37 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.06, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 21.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.87 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Rates (-4.1% vs market -64.2%) |
| `tail_risk` | info | VaR95 -4.54%, CVaR95 -6.99%, CVaR99 -11.05%, worst bar -19.31%, longest recovery 652 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.78); top-5 symbols give 59% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 34.15% to 47.28% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.11, median 0.86, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.89 vs 0.12 median on 100 synthetic markets (p = 0.040) |
| `noise_injection` | pass | net Sharpe 0.89 -> 0.9365 at 0.1x, 0.9372 at 0.25x, 0.8886 at 0.5x |
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
| 0.33 | 0.06 | 0.21 | -0.53 | 0.02 | 0.00 | 0.63 | 0.02 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 0.78 | 0.06 | 2.20 |
| 2018 | 2.26 | 1.23 | -0.73 |
| 2019 | 0.68 | 0.13 | 0.94 |
| 2020 | 2.20 | 0.54 | 3.02 |
| 2021 | 2.52 | 1.09 | 0.60 |
| 2022 | -1.19 | -0.19 | -0.64 |
| 2023 | -1.54 | -0.21 | 1.56 |
| 2024 | -0.50 | -0.10 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
