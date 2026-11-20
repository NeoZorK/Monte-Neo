# Search candidate 43d226ce: hi52 {'window': 200, 'skip': 0} sign 1, top 60 liquid coins: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_hi52. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-57-b80847fa`; planned Lab-wide trials: 134.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 4/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`02edce11ccfec07d`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0455 (t=2.8, ICIR 0.16): the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 0.90, spread 1.6249% per period) |
| `long_short_legs` | pass | short leg earns 34% of the spread; long leg 66% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.100/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.6180%/period; selection effect 1.5671%; with dates shuffled 1.0944% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | warn | the edge does not survive doubled costs: net return +12.6% a year at the modelled costs, -1.2% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | pass | at AUM 5e+04: gross 38.15%, impact 18.67%, net 18.19% per year |
| `participation_limit` | pass | participation p95 0.41%, max 37.24% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 2.28e+05 and reaches zero at 2.28e+05 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 5% of short exposure in the least liquid 20%; borrow 2.78%/yr vs short-leg profit -37.14%/yr |
| `turnover_vs_decay` | info | holding 10.2 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 3.49%, median 15.74%, max 33.34% (k=21) |
| `factor_exposure` | info | factors explain 22% of return variance; strongest: market (beta -0.21, t -9.0), reversal (beta -0.24, t -6.3) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 2.8 is below the Harvey-Liu-Zhu hurdle of 3.0 |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 1.99 (+0.30) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.3) |
| `market_timing_beta` | info | up beta -0.25, down beta -0.26 (timing t 0.2) |
| `crowding` | info | correlation with momentum +0.19, low_vol +0.15; mean return on momentum crash days -0.0123 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.36) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 0.74, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 156.7 years needed to separate Sharpe 0.25 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 92.0% vs 61.0%..99.2% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.25 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.034 over 134 trial(s) on net returns (Sharpe 0.25 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.26, mean net exposure -0.05 |
| `concentration` | warn | median effective positions 18.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.80 (max 2.00), net -0.05; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Rates (-32.0% vs market -64.2%) |
| `tail_risk` | info | VaR95 -4.86%, CVaR95 -7.19%, CVaR99 -11.08%, worst bar -15.40%, longest recovery 1070 bars |
| `universe_subsampling` | warn | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.65); top-5 symbols give 105% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 26.32% to 45.35% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.23, median 0.25, 80% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.52 vs 0.36 median on 100 synthetic markets (p = 0.307): not distinguishable from the market-only null |
| `noise_injection` | pass | net Sharpe 0.52 -> 0.5877 at 0.1x, 0.657 at 0.25x, 0.6354 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **NEEDS_MORE_EVIDENCE**, ARL **4/9**. ARL 4/9 — blocked at 5: it is new alpha (residual_alpha)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.65 | 0.55 | 0.64 | -0.35 | 0.14 | 0.02 | 1.09 | 0.09 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | 0.11 | -0.01 | -0.73 |
| 2019 | 0.82 | 0.17 | 0.94 |
| 2020 | 2.61 | 0.85 | 3.02 |
| 2021 | 1.78 | 0.70 | 0.60 |
| 2022 | -1.01 | -0.20 | -0.64 |
| 2023 | 1.24 | 0.20 | 1.56 |
| 2024 | 0.15 | 0.01 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
