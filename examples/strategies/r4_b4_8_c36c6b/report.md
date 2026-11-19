# Search candidate c36c6b3e: bab {'window': 30} sign -1, top 60 liquid coins: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_bab. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-56-cab30334`; planned Lab-wide trials: 134.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 1 |
| validation | pre | REJECT | 2/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`51c661b02a0a6a30`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0257 (t=2.1, ICIR 0.09): the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | warn | bucket returns are not monotone (25% adjacent increases, rank corr -0.50): profit may sit in one extreme |
| `long_short_legs` | info | the top-minus-bottom spread is not positive; no profit to split |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | fail | **FAILED.**  real spread Sharpe -0.025/period is not above permuted-score placebos (p=0.905): the spread does not earn |
| `selection_vs_timing` | info | spread -0.2178%/period; selection effect -0.2349%; with dates shuffled 0.2816% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | fail | **FAILED.**  the portfolio does not earn after costs: net return -55.3% a year at the modelled costs, -74.0% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | fail | **FAILED.**  at AUM 5e+04: gross -53.12%, impact 25.69%, net -80.20% per year |
| `participation_limit` | pass | participation p95 1.68%, max 61.86% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 6% of short exposure in the least liquid 20%; borrow 2.95%/yr vs short-leg profit -62.02%/yr |
| `turnover_vs_decay` | info | holding 10.1 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min -36.02%, median -25.65%, max -10.91% (k=21) |
| `factor_exposure` | info | factors explain 22% of return variance; strongest: market (beta -0.18, t -8.9), low_vol (beta +0.25, t +4.8) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? no significant residual alpha (t -2.4) |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 1.87 (+0.19) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew -0.6) |
| `market_timing_beta` | info | up beta -0.30, down beta -0.23 (timing t -1.1) |
| `crowding` | info | correlation with momentum -0.02, low_vol +0.36; mean return on momentum crash days +0.0060 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.39) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = -3.19, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | warn | How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; Sharpe -0.99 is not positive, so no length of history separates it from luck |
| `drawdown_plausibility` | pass | max drawdown 100.0% vs 99.4%..100.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe -0.99 becomes -0.42 after Bonferroni for 134 trials (haircut 57%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.000 over 134 trial(s) on net returns (Sharpe -0.99 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | warn | mean rolling beta -0.31, mean net exposure -0.04: declared neutral but is not |
| `concentration` | warn | median effective positions 24.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.92 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Rates (-27.3% vs market -64.2%) |
| `tail_risk` | info | VaR95 -5.34%, CVaR95 -8.59%, CVaR99 -15.93%, worst bar -51.77%, longest recovery 2644 bars |
| `universe_subsampling` | fail | **FAILED.**  0% of 100 random 70% subsets earn a positive net return (median Sharpe -0.48); top-5 symbols give no share of the profit (there is no gross profit): the result does not hold on most subsets |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges -36.65% to -25.14% |
| `cpcv_paths` | warn | net Sharpe over 15 test combinations: min -1.30, median -0.68, 0% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe -0.66 vs 0.21 median on 100 synthetic markets (p = 0.990): not distinguishable from the market-only null |
| `noise_injection` | skip | net Sharpe -0.66 is not positive: nothing to degrade |
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
| -0.55 | -0.76 | -0.42 | -0.62 | 0.21 | 0.04 | -1.47 | 0.00 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 2.17 | 0.41 | 2.20 |
| 2018 | 0.17 | -0.01 | -0.73 |
| 2019 | 1.30 | 0.28 | 0.94 |
| 2020 | 1.37 | 0.35 | 3.02 |
| 2021 | -0.03 | -0.04 | 0.60 |
| 2022 | -1.43 | -0.26 | -0.64 |
| 2023 | -0.07 | -0.02 | 1.56 |
| 2024 | -0.76 | -0.16 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
