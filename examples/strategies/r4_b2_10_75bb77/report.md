# Search candidate 75bb775f: comp_MLI {'parts': ['M', 'L', 'I']} sign 1, top 30 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_comp_MLI. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-28-58379444`; planned Lab-wide trials: 114.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`5732806a95e9440e`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0073 (t=0.5): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | warn | bucket returns are not monotone (75% adjacent increases, rank corr 0.70): profit may sit in one extreme |
| `long_short_legs` | pass | short leg earns 63% of the spread; long leg 37% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.107/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.5322%/period; selection effect 1.5346%; with dates shuffled -0.5132% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | warn | the edge does not survive doubled costs: net return +0.6% a year at the modelled costs, -15.1% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | warn | at AUM 5e+04: gross 23.62%, impact 21.31%, net 0.87% per year |
| `participation_limit` | pass | participation p95 0.91%, max 17.31% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 1% of short exposure in the least liquid 20%; borrow 2.88%/yr vs short-leg profit -34.06%/yr |
| `turnover_vs_decay` | info | holding 9.5 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 3.55%, median 23.00%, max 40.84% (k=21) |
| `factor_exposure` | info | factors explain 2% of return variance; strongest: momentum (beta +0.18, t +3.6), size (beta +0.14, t +2.8) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? no significant residual alpha (t 1.4) |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 1.76 (+0.08) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.2) |
| `market_timing_beta` | info | up beta -0.01, down beta -0.04 (timing t 0.6) |
| `crowding` | info | correlation with momentum +0.12, low_vol +0.00; mean return on momentum crash days -0.0055 |
| `known_anomaly_match` | info | closest known factor: momentum (corr +0.12) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 0.03, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 81443.8 years needed to separate Sharpe 0.01 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 92.3% vs 73.8%..99.9% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.01 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.005 over 134 trial(s) on net returns (Sharpe 0.01 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.06, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 10.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.88 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Volmageddon (-0.3% vs market -0.3%) |
| `tail_risk` | info | VaR95 -4.98%, CVaR95 -8.10%, CVaR99 -13.40%, worst bar -24.67%, longest recovery 1124 bars |
| `universe_subsampling` | warn | 91% of 100 random 70% subsets earn a positive net return (median Sharpe 0.28); top-5 symbols give 172% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 16.29% to 32.98% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.49, median 0.27, 67% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.30 vs -0.08 median on 100 synthetic markets (p = 0.099) |
| `noise_injection` | pass | net Sharpe 0.30 -> 0.3198 at 0.1x, 0.3203 at 0.25x, 0.3308 at 0.5x |
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
| -0.14 | -0.26 | -0.20 | -0.31 | 0.06 | 0.00 | -0.37 | 0.00 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 2.35 | 0.35 | 2.20 |
| 2018 | -0.21 | -0.12 | -0.73 |
| 2019 | 0.98 | 0.18 | 0.94 |
| 2020 | 1.85 | 0.52 | 3.02 |
| 2021 | -0.08 | -0.06 | 0.60 |
| 2022 | -0.17 | -0.05 | -0.64 |
| 2023 | 1.17 | 0.20 | 1.56 |
| 2024 | -1.14 | -0.26 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
