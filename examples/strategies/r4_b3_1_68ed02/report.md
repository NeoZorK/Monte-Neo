# Search candidate 68ed02db: comp_LHI {'parts': ['L', 'H', 'I']} sign 1, top 30 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_comp_LHI. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-38-82714fb1`; planned Lab-wide trials: 124.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 4/9 | n/a | n/a | 1 |
| validation | pre | PASS_WITH_WARNINGS | 5/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`cff3b649bbda4bf7`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0492 (t=4.5, ICIR 0.15): the signal predicts returns |
| `ic_decay` | info | best horizon 16; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 0.8436% per period) |
| `long_short_legs` | pass | short leg earns 39% of the spread; long leg 61% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.149/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 0.8436%/period; selection effect 0.8355%; with dates shuffled 0.1536% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | pass | net return +51.3% a year at the modelled costs, +41.6% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | pass | at AUM 5e+04: gross 88.32%, impact 12.87%, net 74.30% per year |
| `participation_limit` | pass | participation p95 0.32%, max 20.88% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 1.18e+06 and reaches zero at 2.68e+06 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 0% of short exposure in the least liquid 20%; borrow 2.59%/yr vs short-leg profit -14.46%/yr |
| `turnover_vs_decay` | info | holding 10.5 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 9.46%, median 32.73%, max 55.91% (k=21) |
| `factor_exposure` | info | factors explain 15% of return variance; strongest: market (beta -0.20, t -4.9), momentum (beta +0.20, t +3.8) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 3.7 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.13 (+0.44) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.8) |
| `market_timing_beta` | info | up beta -0.27, down beta -0.27 (timing t 0.0) |
| `crowding` | info | correlation with momentum +0.10, low_vol +0.24; mean return on momentum crash days +0.0006 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.34) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | warn | t = 2.87 is above 2 but below the Harvey-Liu-Zhu hurdle of 3.0 |
| `min_backtest_length` | warn | How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 11.3 years needed to separate Sharpe 0.93 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 74.7% vs 51.1%..92.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.93 becomes 0.31 after Bonferroni for 134 trials (haircut 67%) |
| `deflated_sharpe` | warn | The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.662 over 134 trial(s) on net returns (Sharpe 0.93 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.29, mean net exposure -0.08 |
| `concentration` | warn | median effective positions 8.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.65 (max 2.00), net -0.08; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Volmageddon (0.0% vs market -0.3%) |
| `tail_risk` | info | VaR95 -4.72%, CVaR95 -7.57%, CVaR99 -12.21%, worst bar -18.89%, longest recovery 571 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.92); top-5 symbols give 63% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 60.93% to 78.22% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.02, median 1.14, 93% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 1.11 vs 0.02 median on 100 synthetic markets (p = 0.010) |
| `noise_injection` | pass | net Sharpe 1.11 -> 1.1027 at 0.1x, 1.0423 at 0.25x, 0.9879 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **PASS_WITH_WARNINGS**, ARL **5/9**. ARL 5/9 — blocked at 6: it survives the search (deflated_sharpe, hlz_hurdle, min_backtest_length)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 1.29 | 1.08 | 2.01 | -0.20 | 0.24 | 0.06 | 2.27 | 0.48 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | -1.73 | -0.39 | -0.73 |
| 2019 | 4.24 | 1.81 | 0.94 |
| 2020 | 3.16 | 1.21 | 3.02 |
| 2021 | 1.88 | 0.74 | 0.60 |
| 2022 | 1.39 | 0.30 | -0.64 |
| 2023 | 1.48 | 0.27 | 1.56 |
| 2024 | 0.34 | 0.05 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
