# Search candidate f02299ee: comp_VH {'parts': ['V', 'H']} sign 1, top 30 liquid coins: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_comp_VH. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-52-82d6c8d7`; planned Lab-wide trials: 134.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 4/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 5/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`d2533072ef50637b`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0313 (t=2.8, ICIR 0.09): the signal predicts returns |
| `ic_decay` | info | best horizon 19; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 0.5274% per period) |
| `long_short_legs` | pass | short leg earns 58% of the spread; long leg 42% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.096/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 0.5274%/period; selection effect 0.5325%; with dates shuffled 0.2573% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | pass | net return +30.8% a year at the modelled costs, +17.8% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | pass | at AUM 5e+04: gross 63.58%, impact 17.23%, net 44.69% per year |
| `participation_limit` | pass | participation p95 0.37%, max 13.40% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 5.18e+05 and reaches zero at 1.18e+06 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 0% of short exposure in the least liquid 20%; borrow 2.59%/yr vs short-leg profit -12.01%/yr |
| `turnover_vs_decay` | info | holding 7.2 bars |
| `rebalance_timing_luck` | warn | annual net return by rebalance day: min -6.11%, median 21.20%, max 42.94% (k=21) |
| `factor_exposure` | info | factors explain 13% of return variance; strongest: market (beta -0.18, t -5.0), momentum (beta +0.22, t +4.7) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 3.7 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.13 (+0.44) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.6) |
| `market_timing_beta` | info | up beta -0.22, down beta -0.20 (timing t -0.3) |
| `crowding` | info | correlation with momentum +0.18, low_vol +0.15; mean return on momentum crash days -0.0045 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.29) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 1.98, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 24.2 years needed to separate Sharpe 0.64 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 64.0% vs 51.4%..95.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.64 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.288 over 134 trial(s) on net returns (Sharpe 0.64 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.21, mean net exposure -0.08 |
| `concentration` | warn | median effective positions 8.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.65 (max 2.00), net -0.08; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Crypto winter (-8.1% vs market -59.2%) |
| `tail_risk` | info | VaR95 -4.31%, CVaR95 -6.66%, CVaR99 -10.58%, worst bar -15.51%, longest recovery 500 bars |
| `universe_subsampling` | warn | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.63); top-5 symbols give 95% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 40.62% to 50.10% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.26, median 0.93, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.91 vs 0.12 median on 100 synthetic markets (p = 0.020) |
| `noise_injection` | pass | net Sharpe 0.91 -> 0.8897 at 0.1x, 0.8515 at 0.25x, 0.7719 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **NEEDS_MORE_EVIDENCE**, ARL **5/9**. ARL 5/9 — blocked at 6: it survives the search (deflated_sharpe, min_backtest_length)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.70 | 0.43 | 0.75 | -0.36 | 0.20 | 0.04 | 1.12 | 0.11 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | 0.32 | 0.05 | -0.73 |
| 2019 | 1.76 | 0.60 | 0.94 |
| 2020 | 3.30 | 1.11 | 3.02 |
| 2021 | 2.32 | 0.96 | 0.60 |
| 2022 | -1.21 | -0.24 | -0.64 |
| 2023 | -0.42 | -0.09 | 1.56 |
| 2024 | 1.18 | 0.28 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
