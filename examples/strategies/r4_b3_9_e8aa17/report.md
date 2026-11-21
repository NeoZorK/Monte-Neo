# Search candidate e8aa172c: comp_MLI {'parts': ['M', 'L', 'I']} sign 1, top 60 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_comp_MLI. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-47-0466186e`; planned Lab-wide trials: 124.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 1 |
| validation | pre | REJECT | 2/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`819f346cef5a08cb`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0123 (t=1.6): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 17; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | warn | bucket returns are not monotone (50% adjacent increases, rank corr 0.60): profit may sit in one extreme |
| `long_short_legs` | warn | 1023% of the spread profit comes from the short leg: shorts are often not implementable (borrow, bans, microcaps) |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | fail | **FAILED.**  real spread Sharpe 0.001/period is not above permuted-score placebos (p=0.463): the construction earns, not the signal |
| `selection_vs_timing` | info | spread 0.0031%/period; selection effect -0.0132%; with dates shuffled -0.1092% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | fail | **FAILED.**  the portfolio does not earn after costs: net return -29.0% a year at the modelled costs, -47.3% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | fail | **FAILED.**  at AUM 5e+04: gross -15.37%, impact 25.25%, net -41.98% per year |
| `participation_limit` | pass | participation p95 1.44%, max 59.09% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 2% of short exposure in the least liquid 20%; borrow 2.88%/yr vs short-leg profit -50.18%/yr |
| `turnover_vs_decay` | info | holding 10.0 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min -16.33%, median 2.00%, max 18.43% (k=21) |
| `factor_exposure` | info | factors explain 7% of return variance; strongest: size (beta +0.19, t +5.5), momentum (beta +0.18, t +4.9) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? no significant residual alpha (t -0.6) |
| `factor_spanning` | warn | adds nothing the factors do not have (max Sharpe 1.68 -> 1.70) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew -0.9) |
| `market_timing_beta` | info | up beta -0.12, down beta -0.08 (timing t -0.8) |
| `crowding` | info | correlation with momentum +0.11, low_vol +0.16; mean return on momentum crash days -0.0075 |
| `known_anomaly_match` | info | closest known factor: low_vol (corr +0.16) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = -1.81, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; Sharpe -0.60 is not positive, so no length of history separates it from luck |
| `drawdown_plausibility` | pass | max drawdown 98.9% vs 92.2%..100.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe -0.60 becomes -0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.000 over 134 trial(s) on net returns (Sharpe -0.60 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.13, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 22.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.88 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Rates (-6.3% vs market -64.2%) |
| `tail_risk` | info | VaR95 -4.40%, CVaR95 -7.47%, CVaR99 -13.38%, worst bar -32.77%, longest recovery 2588 bars |
| `universe_subsampling` | fail | **FAILED.**  26% of 100 random 70% subsets earn a positive net return (median Sharpe -0.09); top-5 symbols give no share of the profit (there is no gross profit): the result does not hold on most subsets |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | warn | annual return over 13 start dates ranges -10.87% to 1.44%: the range exceeds the median absolute return |
| `cpcv_paths` | warn | net Sharpe over 15 test combinations: min -0.79, median -0.21, 27% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe -0.22 vs -0.04 median on 100 synthetic markets (p = 0.762): not distinguishable from the market-only null |
| `noise_injection` | skip | net Sharpe -0.22 is not positive: nothing to degrade |
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
| -0.47 | -0.76 | -0.34 | -0.54 | 0.06 | 0.00 | -1.03 | 0.00 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 0.40 | 0.03 | 2.20 |
| 2018 | -0.16 | -0.12 | -0.73 |
| 2019 | 0.86 | 0.15 | 0.94 |
| 2020 | 2.46 | 0.57 | 3.02 |
| 2021 | 0.35 | 0.06 | 0.60 |
| 2022 | -0.54 | -0.10 | -0.64 |
| 2023 | 0.65 | 0.08 | 1.56 |
| 2024 | -2.74 | -0.36 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
