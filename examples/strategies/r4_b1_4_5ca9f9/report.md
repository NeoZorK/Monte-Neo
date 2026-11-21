# Search candidate 5ca9f9d3: voltrend {'lookback': 5, 'volume_window': 60} sign 1, top 60 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_voltrend. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-25-8a8d9aa3`; planned Lab-wide trials: 104.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 1 |
| validation | pre | REJECT | 2/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`8dd9651834b79786`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0069 (t=0.8): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 17; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 1.4189% per period) |
| `long_short_legs` | pass | short leg earns 52% of the spread; long leg 48% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.155/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.4189%/period; selection effect 1.4251%; with dates shuffled 0.1289% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | fail | **FAILED.**  the portfolio does not earn after costs: net return -15.6% a year at the modelled costs, -86.0% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | fail | **FAILED.**  at AUM 5e+04: gross 79.50%, impact 97.18%, net -22.59% per year |
| `participation_limit` | pass | participation p95 1.75%, max 2654.63% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 6% of short exposure in the least liquid 20%; borrow 2.93%/yr vs short-leg profit 1.94%/yr |
| `turnover_vs_decay` | info | holding 2.8 bars |
| `rebalance_timing_luck` | warn | annual net return by rebalance day: min -10.13%, median 12.04%, max 53.24% (k=21) |
| `factor_exposure` | info | factors explain 34% of return variance; strongest: reversal (beta -0.66, t -18.8), size (beta -0.08, t -2.0) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 4.7 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.34 (+0.65) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.5) |
| `market_timing_beta` | info | up beta -0.09, down beta -0.07 (timing t -0.5) |
| `crowding` | info | correlation with momentum -0.08, low_vol +0.01; mean return on momentum crash days +0.0149 |
| `known_anomaly_match` | info | closest known factor: reversal (corr -0.58) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = -0.85, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; Sharpe -0.27 is not positive, so no length of history separates it from luck |
| `drawdown_plausibility` | pass | max drawdown 99.0% vs 86.9%..100.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe -0.27 becomes -0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.000 over 134 trial(s) on net returns (Sharpe -0.27 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.09, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 23.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.91 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Rates (-30.1% vs market -64.2%) |
| `tail_risk` | info | VaR95 -4.91%, CVaR95 -7.65%, CVaR99 -12.64%, worst bar -21.88%, longest recovery 749 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.80); top-5 symbols give 56% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 45.95% to 66.72% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.10, median 0.98, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.97 vs -0.03 median on 100 synthetic markets (p = 0.010) |
| `noise_injection` | pass | net Sharpe 0.97 -> 0.8665 at 0.1x, 0.7098 at 0.25x, 0.6355 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **REJECT**, ARL **2/9**. ARL 2/9 — blocked at 3: it earns after costs (cost_sensitivity, market_impact)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.80 | 0.25 | 0.79 | -0.34 | 0.00 | 0.00 | 1.60 | 0.15 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 2.19 | 0.36 | 2.20 |
| 2018 | 2.57 | 1.47 | -0.73 |
| 2019 | -0.24 | -0.06 | 0.94 |
| 2020 | 1.99 | 0.54 | 3.02 |
| 2021 | 2.95 | 1.25 | 0.60 |
| 2022 | 0.59 | 0.09 | -0.64 |
| 2023 | -0.93 | -0.12 | 1.56 |
| 2024 | -0.83 | -0.17 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
