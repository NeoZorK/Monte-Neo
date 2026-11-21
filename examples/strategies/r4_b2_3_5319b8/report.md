# Search candidate 5319b885: comp_BH {'parts': ['B', 'H']} sign 1, top 30 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_comp_BH. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-31-dce5278f`; planned Lab-wide trials: 114.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 4/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`688503a5b3ee8f51`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0765 (t=3.7, ICIR 0.22): the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 2.5367% per period) |
| `long_short_legs` | pass | short leg earns 30% of the spread; long leg 70% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.176/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 2.5367%/period; selection effect 2.4647%; with dates shuffled 1.4670% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | pass | net return +26.3% a year at the modelled costs, +17.8% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | pass | at AUM 5e+04: gross 50.37%, impact 11.26%, net 38.12% per year |
| `participation_limit` | pass | participation p95 0.30%, max 17.75% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 5.18e+05 and reaches zero at 1.18e+06 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 0% of short exposure in the least liquid 20%; borrow 2.59%/yr vs short-leg profit -30.43%/yr |
| `turnover_vs_decay` | info | holding 12.2 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 13.52%, median 27.57%, max 47.82% (k=21) |
| `factor_exposure` | info | factors explain 20% of return variance; strongest: market (beta -0.28, t -6.6), momentum (beta +0.27, t +5.0) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 2.3 is below the Harvey-Liu-Zhu hurdle of 3.0 |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 1.88 (+0.19) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.5) |
| `market_timing_beta` | info | up beta -0.35, down beta -0.33 (timing t -0.2) |
| `crowding` | info | correlation with momentum +0.15, low_vol +0.24; mean return on momentum crash days -0.0065 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.41) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 1.44, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 45.3 years needed to separate Sharpe 0.47 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 88.6% vs 60.9%..98.8% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.47 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.132 over 134 trial(s) on net returns (Sharpe 0.47 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | warn | mean rolling beta -0.36, mean net exposure -0.08: declared neutral but is not |
| `concentration` | warn | median effective positions 8.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.65 (max 2.00), net -0.08; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: SVB (-22.1% vs market 6.7%) |
| `tail_risk` | info | VaR95 -5.11%, CVaR95 -8.21%, CVaR99 -12.95%, worst bar -18.89%, longest recovery 932 bars |
| `universe_subsampling` | warn | 98% of 100 random 70% subsets earn a positive net return (median Sharpe 0.48); top-5 symbols give 121% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 33.86% to 44.15% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.46, median 0.77, 80% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.61 vs 0.12 median on 100 synthetic markets (p = 0.149): not distinguishable from the market-only null |
| `noise_injection` | pass | net Sharpe 0.61 -> 0.6565 at 0.1x, 0.619 at 0.25x, 0.6158 at 0.5x |
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
| 0.64 | 0.55 | 0.68 | -0.37 | 0.30 | 0.09 | 0.85 | 0.09 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | -1.64 | -0.41 | -0.73 |
| 2019 | 2.54 | 0.89 | 0.94 |
| 2020 | 3.08 | 1.25 | 3.02 |
| 2021 | 0.97 | 0.30 | 0.60 |
| 2022 | -0.39 | -0.11 | -0.64 |
| 2023 | 0.65 | 0.12 | 1.56 |
| 2024 | 1.24 | 0.29 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
