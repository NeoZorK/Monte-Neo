# Betting against beta: long low-beta, short high-beta coins (BTC-hedged): automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: cross_section. Fixed parameters (chosen before any data was read): `{"beta_window": 90, "horizon": 7}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-18-8ffde117`; planned Lab-wide trials: 98.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 3 |
| validation | pre | NEEDS_MORE_EVIDENCE | 4/9 | n/a | n/a | 98 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`91b13ce201457040`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0507 (t=3.1, ICIR 0.14): the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 1.2224% per period) |
| `long_short_legs` | pass | short leg earns 34% of the spread; long leg 66% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.098/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.2224%/period; selection effect 1.2231%; with dates shuffled 0.3876% (a time-invariant tilt or market timing, not stock selection) |
| `market_impact` | pass | at AUM 5e+04: gross 14.02%, impact 6.39%, net 7.15% per year |
| `participation_limit` | pass | participation p95 0.41%, max 20.87% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 2.28e+05 and reaches zero at 2.28e+05 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 15% of short exposure in the least liquid 20%; borrow 2.90%/yr vs short-leg profit -78.84%/yr |
| `turnover_vs_decay` | info | holding 28.5 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 22.21%, median 30.93%, max 45.20% (k=21) |
| `factor_exposure` | info | factors explain 27% of return variance; strongest: low_vol (beta +0.36, t +4.3), market (beta -0.13, t -2.8) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 2.1 is below the Harvey-Liu-Zhu hurdle of 3.0 |
| `factor_spanning` | info | max Sharpe rises 1.38 -> 1.52 (+0.14) |
| `hidden_short_volatility` | warn | short-option payoff signs: skew -4.8, excess kurtosis 127.1 |
| `market_timing_beta` | info | up beta -0.41, down beta -0.21 (timing t -0.9) |
| `crowding` | info | correlation with momentum +0.06, low_vol +0.47; mean return on momentum crash days -0.0022 |
| `known_anomaly_match` | info | closest known factor: low_vol (corr +0.47) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 0.43, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 505.1 years needed to separate Sharpe 0.13 from the best of 98 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 99.9% vs 80.6%..100.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.13 becomes 0.00 after Bonferroni for 98 trials (haircut 100%) |
| `neutrality` | warn | mean rolling beta -0.39, mean net exposure -0.09: declared neutral but is not |
| `concentration` | warn | median effective positions 6.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.84 (max 2.00), net -0.09; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Volmageddon (-9.5% vs market -2.5%) |
| `tail_risk` | info | VaR95 -5.88%, CVaR95 -10.12%, CVaR99 -19.47%, worst bar -99.11%, longest recovery 2600 bars |
| `universe_subsampling` | warn | 88% of 100 random 70% subsets earn a positive net return (median Sharpe 0.18); top-5 symbols give 479% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | warn | annual return over 13 start dates ranges 9.67% to 39.83%: the range exceeds the median absolute return |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.63, median 0.10, 60% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.13 vs 0.08 median on 100 synthetic markets (p = 0.446): not distinguishable from the market-only null |
| `noise_injection` | pass | net Sharpe 0.13 -> 0.1234 at 0.1x, 0.0586 at 0.25x, 0.0645 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **NEEDS_MORE_EVIDENCE**, ARL **4/9**. ARL 4/9 — blocked at 5: it is new alpha (hidden_short_volatility, residual_alpha)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 1.20 | 1.17 | 2.94 | -0.41 | 0.20 | 0.04 | 2.14 | 0.46 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 1.09 | 0.15 | 2.20 |
| 2018 | -0.85 | -0.36 | -0.73 |
| 2019 | 1.92 | 0.49 | 0.94 |
| 2020 | 0.85 | 0.19 | 3.02 |
| 2021 | 1.30 | 0.74 | 0.60 |
| 2022 | 1.34 | 0.28 | -0.64 |
| 2023 | 0.98 | 0.20 | 1.56 |
| 2024 | 1.90 | 0.48 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
