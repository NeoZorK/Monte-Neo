# Search candidate 2fbb8ee2: bab2 {'window': 200} sign -1, top 30 liquid coins: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_bab2. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-46-023dca5f`; planned Lab-wide trials: 124.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 4/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`0d4f445180c2425f`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0562 (t=3.0, ICIR 0.17): the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | warn | bucket returns are not monotone (50% adjacent increases, rank corr 0.60): profit may sit in one extreme |
| `long_short_legs` | pass | short leg earns 20% of the spread; long leg 80% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.088/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.1813%/period; selection effect 1.1851%; with dates shuffled 1.2159% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | pass | net return +18.5% a year at the modelled costs, +13.6% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | pass | at AUM 5e+04: gross 34.06%, impact 6.72%, net 26.86% per year |
| `participation_limit` | pass | participation p95 0.70%, max 16.44% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 5.18e+05 and reaches zero at 2.68e+06 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 2% of short exposure in the least liquid 20%; borrow 2.78%/yr vs short-leg profit -25.48%/yr |
| `turnover_vs_decay` | info | holding 27.7 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 12.83%, median 26.92%, max 47.43% (k=21) |
| `factor_exposure` | info | factors explain 15% of return variance; strongest: size (beta +0.26, t +7.1), market (beta -0.17, t -5.0) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? no significant residual alpha (t 1.0) |
| `factor_spanning` | warn | adds nothing the factors do not have (max Sharpe 1.68 -> 1.72) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.2) |
| `market_timing_beta` | info | up beta -0.22, down beta -0.24 (timing t 0.2) |
| `crowding` | info | correlation with momentum +0.05, low_vol +0.24; mean return on momentum crash days -0.0027 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.32) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 1.17, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 71.7 years needed to separate Sharpe 0.37 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 82.8% vs 58.2%..98.5% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.37 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.077 over 134 trial(s) on net returns (Sharpe 0.37 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.29, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 10.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.81 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: SVB (-14.9% vs market 6.7%) |
| `tail_risk` | info | VaR95 -5.00%, CVaR95 -7.42%, CVaR99 -11.38%, worst bar -17.46%, longest recovery 851 bars |
| `universe_subsampling` | warn | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.44); top-5 symbols give 136% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 23.46% to 28.81% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.25, median 0.49, 80% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.47 vs 0.22 median on 100 synthetic markets (p = 0.317): not distinguishable from the market-only null |
| `noise_injection` | pass | net Sharpe 0.47 -> 0.4223 at 0.1x, 0.4009 at 0.25x, 0.384 at 0.5x |
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
| 1.13 | 1.06 | 1.73 | -0.30 | 0.38 | 0.14 | 1.80 | 0.35 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | -0.99 | -0.28 | -0.73 |
| 2019 | 1.49 | 0.36 | 0.94 |
| 2020 | 3.10 | 1.00 | 3.02 |
| 2021 | 1.09 | 0.32 | 0.60 |
| 2022 | 1.67 | 0.45 | -0.64 |
| 2023 | 0.81 | 0.16 | 1.56 |
| 2024 | 0.94 | 0.23 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
