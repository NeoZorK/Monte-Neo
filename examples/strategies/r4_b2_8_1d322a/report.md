# Search candidate 1d322ac2: resmom {'lookback': 180, 'beta_window': 90} sign -1, top 30 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_resmom. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-36-7e415907`; planned Lab-wide trials: 114.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 3/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 4/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`f547d8c5f089a92d`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0411 (t=2.3, ICIR 0.13): the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | warn | bucket returns are not monotone (50% adjacent increases, rank corr -0.20): profit may sit in one extreme |
| `long_short_legs` | pass | short leg earns 51% of the spread; long leg 49% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.034/period beats permuted-score placebos (p=0.035) |
| `selection_vs_timing` | info | spread 0.4432%/period; selection effect 0.4333%; with dates shuffled 0.0263% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | warn | the edge does not survive doubled costs: net return +9.2% a year at the modelled costs, -1.2% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | pass | at AUM 5e+04: gross 28.33%, impact 14.07%, net 13.27% per year |
| `participation_limit` | pass | participation p95 0.53%, max 32.46% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 2.28e+05 and reaches zero at 2.28e+05 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 1% of short exposure in the least liquid 20%; borrow 2.70%/yr vs short-leg profit -39.64%/yr |
| `turnover_vs_decay` | info | holding 12.9 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min -3.98%, median 17.06%, max 31.54% (k=21) |
| `factor_exposure` | info | factors explain 22% of return variance; strongest: momentum (beta -0.47, t -9.5), low_vol (beta +0.26, t +7.2) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? no significant residual alpha (t 0.9) |
| `factor_spanning` | warn | adds nothing the factors do not have (max Sharpe 1.68 -> 1.71) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.1) |
| `market_timing_beta` | info | up beta -0.15, down beta -0.14 (timing t -0.2) |
| `crowding` | info | correlation with momentum -0.35, low_vol +0.31; mean return on momentum crash days +0.0268 |
| `known_anomaly_match` | info | closest known factor: momentum (corr -0.35) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 0.60, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 268.0 years needed to separate Sharpe 0.19 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 86.7% vs 61.2%..99.1% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.19 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.022 over 134 trial(s) on net returns (Sharpe 0.19 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.12, mean net exposure -0.05 |
| `concentration` | warn | median effective positions 8.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.75 (max 2.00), net -0.05; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: FTX (-21.4% vs market -31.4%) |
| `tail_risk` | info | VaR95 -4.41%, CVaR95 -6.91%, CVaR99 -11.12%, worst bar -16.06%, longest recovery 1738 bars |
| `universe_subsampling` | warn | 94% of 100 random 70% subsets earn a positive net return (median Sharpe 0.24); top-5 symbols give 168% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | warn | annual return over 13 start dates ranges -0.45% to 21.71%: a later start loses while the full sample wins |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.43, median 0.36, 67% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.41 vs -0.16 median on 100 synthetic markets (p = 0.050) |
| `noise_injection` | pass | net Sharpe 0.41 -> 0.2957 at 0.1x, 0.3049 at 0.25x, 0.2639 at 0.5x |
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
| 0.15 | 0.07 | 0.03 | -0.48 | 0.09 | 0.01 | 0.15 | 0.01 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | 0.84 | 0.24 | -0.73 |
| 2019 | 0.46 | 0.07 | 0.94 |
| 2020 | 1.10 | 0.28 | 3.02 |
| 2021 | -1.19 | -0.34 | 0.60 |
| 2022 | 2.65 | 0.70 | -0.64 |
| 2023 | 0.42 | 0.07 | 1.56 |
| 2024 | -0.56 | -0.14 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
