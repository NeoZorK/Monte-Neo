# Search candidate f8e6f47c: comp_ML {'parts': ['M', 'L']} sign 1, top 30 liquid coins: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_comp_ML. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-34-12dd1ceb`; planned Lab-wide trials: 114.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 1 |
| validation | pre | REJECT | 2/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`a365f8d26b374e3c`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0794 (t=5.6, ICIR 0.25): the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | warn | bucket returns are not monotone (75% adjacent increases, rank corr 0.70): profit may sit in one extreme |
| `long_short_legs` | pass | short leg earns 37% of the spread; long leg 63% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.063/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 0.6441%/period; selection effect 0.6706%; with dates shuffled 0.6346% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | fail | **FAILED.**  the portfolio does not earn after costs: net return -2.7% a year at the modelled costs, -16.8% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | fail | **FAILED.**  at AUM 5e+04: gross 16.41%, impact 18.98%, net -3.94% per year |
| `participation_limit` | pass | participation p95 0.78%, max 14.29% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 7% of short exposure in the least liquid 20%; borrow 2.88%/yr vs short-leg profit -47.09%/yr |
| `turnover_vs_decay` | info | holding 10.0 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min -13.20%, median 11.61%, max 29.90% (k=21) |
| `factor_exposure` | info | factors explain 18% of return variance; strongest: market (beta -0.20, t -8.0), low_vol (beta +0.27, t +5.8) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? no significant residual alpha (t 1.4) |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 1.75 (+0.07) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew -0.5) |
| `market_timing_beta` | info | up beta -0.31, down beta -0.25 (timing t -1.0) |
| `crowding` | info | correlation with momentum +0.11, low_vol +0.33; mean return on momentum crash days -0.0067 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.36) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = -0.14, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; Sharpe -0.05 is not positive, so no length of history separates it from luck |
| `drawdown_plausibility` | pass | max drawdown 94.9% vs 78.9%..99.9% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe -0.05 becomes -0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.003 over 134 trial(s) on net returns (Sharpe -0.05 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | warn | mean rolling beta -0.32, mean net exposure -0.04: declared neutral but is not |
| `concentration` | warn | median effective positions 10.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.88 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Volmageddon (-0.3% vs market -0.3%) |
| `tail_risk` | info | VaR95 -5.63%, CVaR95 -9.38%, CVaR99 -15.35%, worst bar -27.87%, longest recovery 2588 bars |
| `universe_subsampling` | warn | 92% of 100 random 70% subsets earn a positive net return (median Sharpe 0.19); top-5 symbols give 244% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | warn | annual return over 13 start dates ranges 8.30% to 27.57%: the range exceeds the median absolute return |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.25, median 0.25, 60% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.20 vs 0.26 median on 100 synthetic markets (p = 0.594): not distinguishable from the market-only null |
| `noise_injection` | pass | net Sharpe 0.20 -> 0.1797 at 0.1x, 0.2717 at 0.25x, 0.201 at 0.5x |
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
| 0.42 | 0.27 | 0.35 | -0.32 | 0.14 | 0.02 | 0.63 | 0.04 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 2.50 | 0.39 | 2.20 |
| 2018 | 0.11 | -0.03 | -0.73 |
| 2019 | 1.25 | 0.27 | 0.94 |
| 2020 | 1.92 | 0.61 | 3.02 |
| 2021 | -0.39 | -0.17 | 0.60 |
| 2022 | 0.58 | 0.11 | -0.64 |
| 2023 | 1.50 | 0.29 | 1.56 |
| 2024 | 0.64 | 0.14 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
