# Search candidate 18bcb0d1: comp_LHI {'parts': ['L', 'H', 'I']} sign 1, top 60 liquid coins: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_comp_LHI. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-50-cf1c740d`; planned Lab-wide trials: 134.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 4/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 4/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`d4dee7dd8e53554f`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0480 (t=5.0, ICIR 0.17): the signal predicts returns |
| `ic_decay` | info | best horizon 16; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 0.90, spread 0.7726% per period) |
| `long_short_legs` | pass | short leg earns 36% of the spread; long leg 64% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.130/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 0.7726%/period; selection effect 0.7744%; with dates shuffled 0.0759% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | pass | net return +36.0% a year at the modelled costs, +25.7% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | pass | at AUM 5e+04: gross 67.10%, impact 13.92%, net 52.19% per year |
| `participation_limit` | pass | participation p95 0.35%, max 36.90% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 5.18e+05 and reaches zero at 1.18e+06 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 0% of short exposure in the least liquid 20%; borrow 2.59%/yr vs short-leg profit -32.22%/yr |
| `turnover_vs_decay` | info | holding 12.1 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 26.13%, median 41.99%, max 50.40% (k=21) |
| `factor_exposure` | info | factors explain 18% of return variance; strongest: market (beta -0.19, t -4.9), momentum (beta +0.17, t +3.4) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 2.7 is below the Harvey-Liu-Zhu hurdle of 3.0 |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.00 (+0.32) |
| `hidden_short_volatility` | fail | **FAILED.**  steady gains and rare crashes: the strategy sells insurance |
| `market_timing_beta` | info | up beta -0.34, down beta -0.24 (timing t -1.2) |
| `crowding` | info | correlation with momentum +0.09, low_vol +0.29; mean return on momentum crash days -0.0012 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.36) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | warn | t = 2.01 is above 2 but below the Harvey-Liu-Zhu hurdle of 3.0 |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 21.0 years needed to separate Sharpe 0.68 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 74.7% vs 53.8%..96.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.68 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.354 over 134 trial(s) on net returns (Sharpe 0.68 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.29, mean net exposure -0.08 |
| `concentration` | warn | median effective positions 14.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.65 (max 2.00), net -0.08; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: SVB (-3.4% vs market 6.7%) |
| `tail_risk` | info | VaR95 -4.32%, CVaR95 -7.36%, CVaR99 -13.97%, worst bar -64.56%, longest recovery 627 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.77); top-5 symbols give 66% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 46.29% to 59.36% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.01, median 0.92, 93% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.88 vs 0.01 median on 100 synthetic markets (p = 0.010) |
| `noise_injection` | pass | net Sharpe 0.88 -> 0.9626 at 0.1x, 0.8804 at 0.25x, 0.8564 at 0.5x |
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
| 1.38 | 1.17 | 2.13 | -0.23 | 0.13 | 0.02 | 2.58 | 0.55 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | -1.73 | -0.39 | -0.73 |
| 2019 | 3.58 | 1.38 | 0.94 |
| 2020 | 3.14 | 1.04 | 3.02 |
| 2021 | 2.54 | 1.28 | 0.60 |
| 2022 | 0.35 | 0.04 | -0.64 |
| 2023 | 1.22 | 0.19 | 1.56 |
| 2024 | 0.63 | 0.10 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
