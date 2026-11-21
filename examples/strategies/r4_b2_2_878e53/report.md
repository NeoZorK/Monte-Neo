# Search candidate 878e5333: mom {'lookback': 14, 'skip': 0} sign 1, top 60 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_mom. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-30-ca31bf3b`; planned Lab-wide trials: 114.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`e06afb8176dbb88e`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0166 (t=1.5): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 1.5341% per period) |
| `long_short_legs` | pass | short leg earns 34% of the spread; long leg 66% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.159/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.5341%/period; selection effect 1.5522%; with dates shuffled 0.3094% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | warn | the edge does not survive doubled costs: net return +9.5% a year at the modelled costs, -32.4% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | warn | at AUM 5e+04: gross 74.42%, impact 57.72%, net 13.71% per year |
| `participation_limit` | pass | participation p95 1.94%, max 4858.30% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 10% of short exposure in the least liquid 20%; borrow 2.95%/yr vs short-leg profit -20.70%/yr |
| `turnover_vs_decay` | info | holding 4.7 bars |
| `rebalance_timing_luck` | warn | annual net return by rebalance day: min -10.51%, median 23.13%, max 39.13% (k=21) |
| `factor_exposure` | info | factors explain 25% of return variance; strongest: reversal (beta -0.54, t -12.3), size (beta -0.23, t -4.4) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 4.4 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.27 (+0.59) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew -0.1) |
| `market_timing_beta` | info | up beta -0.13, down beta -0.08 (timing t -0.8) |
| `crowding` | info | correlation with momentum -0.10, low_vol +0.03; mean return on momentum crash days +0.0138 |
| `known_anomaly_match` | info | closest known factor: reversal (corr -0.47) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 0.50, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 386.9 years needed to separate Sharpe 0.16 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 90.9% vs 71.8%..99.8% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.16 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.017 over 134 trial(s) on net returns (Sharpe 0.16 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.09, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 24.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.92 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Rates (-31.8% vs market -64.2%) |
| `tail_risk` | info | VaR95 -4.94%, CVaR95 -8.27%, CVaR99 -15.02%, worst bar -34.74%, longest recovery 772 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.64); top-5 symbols give 60% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 36.49% to 63.51% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.32, median 0.89, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.87 vs 0.13 median on 100 synthetic markets (p = 0.030) |
| `noise_injection` | pass | net Sharpe 0.87 -> 0.8924 at 0.1x, 0.8677 at 0.25x, 0.774 at 0.5x |
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
| -0.03 | -0.38 | -0.12 | -0.42 | -0.03 | 0.00 | -0.01 | 0.00 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 2.56 | 0.59 | 2.20 |
| 2018 | 2.40 | 1.48 | -0.73 |
| 2019 | 0.08 | -0.01 | 0.94 |
| 2020 | 2.67 | 0.87 | 3.02 |
| 2021 | 0.93 | 0.26 | 0.60 |
| 2022 | -1.12 | -0.23 | -0.64 |
| 2023 | -0.37 | -0.07 | 1.56 |
| 2024 | -0.04 | -0.03 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
