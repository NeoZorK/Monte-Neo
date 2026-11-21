# Search candidate 0994badf: comp_BHZ {'parts': ['B', 'H', 'Z']} sign 1, top 60 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_comp_BHZ. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-40-e5f6e44a`; planned Lab-wide trials: 124.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 3/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`de81e3262fddef94`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0211 (t=1.2): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 18; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 2.5607% per period) |
| `long_short_legs` | pass | short leg earns 35% of the spread; long leg 65% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.135/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 2.5607%/period; selection effect 2.5682%; with dates shuffled -0.2486% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | pass | net return +14.0% a year at the modelled costs, +3.1% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | pass | at AUM 5e+04: gross 36.16%, impact 14.80%, net 20.36% per year |
| `participation_limit` | pass | participation p95 0.30%, max 61.95% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 2.28e+05 and reaches zero at 5.18e+05 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 0% of short exposure in the least liquid 20%; borrow 2.59%/yr vs short-leg profit -44.12%/yr |
| `turnover_vs_decay` | info | holding 12.0 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 10.06%, median 24.55%, max 45.08% (k=21) |
| `factor_exposure` | info | factors explain 10% of return variance; strongest: size (beta +0.16, t +3.3), market (beta -0.13, t -3.2) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? no significant residual alpha (t 1.3) |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 1.76 (+0.08) |
| `hidden_short_volatility` | warn | short-option payoff signs: skew -1.8, excess kurtosis 46.7 |
| `market_timing_beta` | info | up beta -0.22, down beta -0.17 (timing t -0.5) |
| `crowding` | info | correlation with momentum +0.06, low_vol +0.16; mean return on momentum crash days +0.0012 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.24) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 0.76, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 141.7 years needed to separate Sharpe 0.26 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 94.2% vs 63.4%..99.4% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.26 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.041 over 134 trial(s) on net returns (Sharpe 0.26 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.20, mean net exposure -0.08 |
| `concentration` | warn | median effective positions 14.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.65 (max 2.00), net -0.08; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: SVB (-13.8% vs market 6.7%) |
| `tail_risk` | info | VaR95 -4.66%, CVaR95 -7.17%, CVaR99 -12.65%, worst bar -63.58%, longest recovery 932 bars |
| `universe_subsampling` | warn | 98% of 100 random 70% subsets earn a positive net return (median Sharpe 0.29); top-5 symbols give 100% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 21.78% to 28.49% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -1.15, median 0.42, 67% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.47 vs -0.06 median on 100 synthetic markets (p = 0.040) |
| `noise_injection` | pass | net Sharpe 0.47 -> 0.498 at 0.1x, 0.4336 at 0.25x, 0.4261 at 0.5x |
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
| 0.34 | 0.24 | 0.22 | -0.40 | 0.17 | 0.03 | 0.43 | 0.03 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | -1.48 | -0.27 | -0.73 |
| 2019 | 2.27 | 0.61 | 0.94 |
| 2020 | 2.45 | 0.81 | 3.02 |
| 2021 | 1.71 | 0.66 | 0.60 |
| 2022 | -1.74 | -0.24 | -0.64 |
| 2023 | 0.15 | 0.01 | 1.56 |
| 2024 | -0.14 | -0.04 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
