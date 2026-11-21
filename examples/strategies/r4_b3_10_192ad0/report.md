# Search candidate 192ad0ce: resmom {'lookback': 30, 'beta_window': 60} sign 1, top 60 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_resmom. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-39-6ae27cb3`; planned Lab-wide trials: 124.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`6b1805913c08854b`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC -0.0123 (t=-1.1): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 13; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 0.90, spread 1.3025% per period) |
| `long_short_legs` | pass | short leg earns 38% of the spread; long leg 62% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.136/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.3025%/period; selection effect 1.2980%; with dates shuffled 0.2441% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | warn | the edge does not survive doubled costs: net return +19.0% a year at the modelled costs, -6.7% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | warn | at AUM 5e+04: gross 64.86%, impact 35.20%, net 27.57% per year |
| `participation_limit` | pass | participation p95 1.31%, max 49.78% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 2.28e+05 and reaches zero at 2.28e+05 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 5% of short exposure in the least liquid 20%; borrow 2.90%/yr vs short-leg profit -27.04%/yr |
| `turnover_vs_decay` | info | holding 6.6 bars |
| `rebalance_timing_luck` | warn | annual net return by rebalance day: min -7.03%, median 17.84%, max 42.01% (k=21) |
| `factor_exposure` | info | factors explain 16% of return variance; strongest: reversal (beta -0.26, t -6.9), size (beta -0.26, t -5.6) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 5.0 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.44 (+0.76) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.5) |
| `market_timing_beta` | info | up beta -0.04, down beta -0.07 (timing t 0.5) |
| `crowding` | info | correlation with momentum +0.04, low_vol -0.16; mean return on momentum crash days +0.0015 |
| `known_anomaly_match` | info | closest known factor: reversal (corr -0.28) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 1.06, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 75.7 years needed to separate Sharpe 0.36 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 73.7% vs 60.6%..99.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.36 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.072 over 134 trial(s) on net returns (Sharpe 0.36 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.08, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 23.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.89 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Rates (-27.5% vs market -64.2%) |
| `tail_risk` | info | VaR95 -4.65%, CVaR95 -7.32%, CVaR99 -12.13%, worst bar -21.88%, longest recovery 1079 bars |
| `universe_subsampling` | warn | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.78); top-5 symbols give 74% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 44.50% to 56.00% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.26, median 0.82, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.85 vs 0.19 median on 100 synthetic markets (p = 0.010) |
| `noise_injection` | pass | net Sharpe 0.85 -> 0.8879 at 0.1x, 0.874 at 0.25x, 0.7629 at 0.5x |
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
| 0.28 | 0.01 | 0.15 | -0.49 | 0.04 | 0.00 | 0.48 | 0.02 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 2.61 | 0.40 | 2.20 |
| 2018 | 1.64 | 0.71 | -0.73 |
| 2019 | 1.32 | 0.29 | 0.94 |
| 2020 | 2.48 | 0.67 | 3.02 |
| 2021 | 2.25 | 0.85 | 0.60 |
| 2022 | -1.17 | -0.22 | -0.64 |
| 2023 | -1.36 | -0.19 | 1.56 |
| 2024 | -0.01 | -0.02 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
