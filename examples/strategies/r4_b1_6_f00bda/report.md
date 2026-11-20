# Search candidate f00bda81: rev {'lookback': 3} sign 1, top 60 liquid coins: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_rev. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-26-13c9c599`; planned Lab-wide trials: 104.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 1 |
| validation | pre | REJECT | 2/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`3c20230b9cf12c3b`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0231 (t=2.7, ICIR 0.09): the signal predicts returns |
| `ic_decay` | info | best horizon 19; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 1.8153% per period) |
| `long_short_legs` | pass | short leg earns 55% of the spread; long leg 45% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.134/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.8153%/period; selection effect 1.8100%; with dates shuffled 0.3640% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | fail | **FAILED.**  the portfolio does not earn after costs: net return -52.6% a year at the modelled costs, -145.9% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | fail | **FAILED.**  at AUM 5e+04: gross 59.01%, impact 128.89%, net -76.20% per year |
| `participation_limit` | pass | participation p95 1.95%, max 4664.94% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 8% of short exposure in the least liquid 20%; borrow 2.95%/yr vs short-leg profit -11.20%/yr |
| `turnover_vs_decay` | info | holding 2.2 bars |
| `rebalance_timing_luck` | warn | annual net return by rebalance day: min -44.49%, median 6.16%, max 61.71% (k=21) |
| `factor_exposure` | info | factors explain 36% of return variance; strongest: reversal (beta -0.70, t -19.3), low_vol (beta +0.06, t +1.4) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 3.7 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.06 (+0.37) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew -0.1) |
| `market_timing_beta` | info | up beta -0.14, down beta -0.09 (timing t -0.6) |
| `crowding` | info | correlation with momentum -0.09, low_vol +0.07; mean return on momentum crash days +0.0145 |
| `known_anomaly_match` | info | closest known factor: reversal (corr -0.59) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = -2.89, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | warn | How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; Sharpe -0.89 is not positive, so no length of history separates it from luck |
| `drawdown_plausibility` | pass | max drawdown 99.9% vs 99.3%..100.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe -0.89 becomes -0.22 after Bonferroni for 134 trials (haircut 75%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.000 over 134 trial(s) on net returns (Sharpe -0.89 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.12, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 24.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.92 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Volmageddon (-45.8% vs market -0.3%) |
| `tail_risk` | info | VaR95 -5.05%, CVaR95 -8.12%, CVaR99 -13.40%, worst bar -35.24%, longest recovery 767 bars |
| `universe_subsampling` | warn | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.50); top-5 symbols give 76% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 27.29% to 49.74% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.03, median 0.70, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.70 vs 0.02 median on 100 synthetic markets (p = 0.059) |
| `noise_injection` | pass | net Sharpe 0.70 -> 0.6993 at 0.1x, 0.6868 at 0.25x, 0.599 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **REJECT**, ARL **2/9**. ARL 2/9 — blocked at 3: it earns after costs (cost_sensitivity, market_impact)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.85 | 0.56 | 0.82 | -0.15 | -0.02 | 0.00 | 1.72 | 0.17 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | -0.33 | -0.08 | 2.20 |
| 2018 | 2.75 | 1.41 | -0.73 |
| 2019 | 0.41 | 0.07 | 0.94 |
| 2020 | 0.88 | 0.17 | 3.02 |
| 2021 | 1.57 | 0.47 | 0.60 |
| 2022 | 0.07 | -0.00 | -0.64 |
| 2023 | 0.31 | 0.03 | 1.56 |
| 2024 | 1.03 | 0.20 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
