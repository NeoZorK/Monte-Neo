# Search candidate c3f413c5: comp_LHZ {'parts': ['L', 'H', 'Z']} sign 1, top 30 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_comp_LHZ. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-49-d0223e9e`; planned Lab-wide trials: 134.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 4/9 | n/a | n/a | 1 |
| validation | pre | PASS_WITH_WARNINGS | 5/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`ebee0998c50b9f67`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0671 (t=3.6, ICIR 0.21): the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 3.5204% per period) |
| `long_short_legs` | pass | short leg earns 36% of the spread; long leg 64% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.244/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 3.5204%/period; selection effect 3.5486%; with dates shuffled 0.3114% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | pass | net return +52.7% a year at the modelled costs, +43.8% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | pass | at AUM 5e+04: gross 89.25%, impact 11.82%, net 76.36% per year |
| `participation_limit` | pass | participation p95 0.32%, max 13.40% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 1.18e+06 and reaches zero at 6.11e+06 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 0% of short exposure in the least liquid 20%; borrow 2.59%/yr vs short-leg profit -10.93%/yr |
| `turnover_vs_decay` | info | holding 11.3 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 28.65%, median 44.06%, max 58.40% (k=21) |
| `factor_exposure` | info | factors explain 14% of return variance; strongest: low_vol (beta +0.22, t +4.4), market (beta -0.18, t -4.1) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 3.4 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.08 (+0.39) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.8) |
| `market_timing_beta` | info | up beta -0.30, down beta -0.22 (timing t -0.8) |
| `crowding` | info | correlation with momentum +0.02, low_vol +0.27; mean return on momentum crash days +0.0068 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.32) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | warn | t = 2.94 is above 2 but below the Harvey-Liu-Zhu hurdle of 3.0 |
| `min_backtest_length` | warn | How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 10.4 years needed to separate Sharpe 0.97 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 69.4% vs 50.0%..91.1% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.97 becomes 0.39 after Bonferroni for 134 trials (haircut 60%) |
| `deflated_sharpe` | warn | The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.708 over 134 trial(s) on net returns (Sharpe 0.97 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.28, mean net exposure -0.08 |
| `concentration` | warn | median effective positions 8.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.65 (max 2.00), net -0.08; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: SVB (-18.4% vs market 6.7%) |
| `tail_risk` | info | VaR95 -4.60%, CVaR95 -7.46%, CVaR99 -12.33%, worst bar -19.69%, longest recovery 641 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.86); top-5 symbols give 49% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 61.58% to 79.03% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.29, median 1.02, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 1.13 vs -0.04 median on 100 synthetic markets (p = 0.010) |
| `noise_injection` | pass | net Sharpe 1.13 -> 1.0891 at 0.1x, 0.9837 at 0.25x, 0.9209 at 0.5x |
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
| 1.01 | 0.90 | 1.23 | -0.28 | 0.04 | 0.00 | 1.96 | 0.27 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | -0.92 | -0.18 | -0.73 |
| 2019 | 3.56 | 1.33 | 0.94 |
| 2020 | 2.60 | 0.89 | 3.02 |
| 2021 | 2.27 | 0.94 | 0.60 |
| 2022 | 0.32 | 0.04 | -0.64 |
| 2023 | 1.36 | 0.23 | 1.56 |
| 2024 | -0.38 | -0.10 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
