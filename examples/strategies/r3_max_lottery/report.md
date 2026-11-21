# Lottery effect: short coins with the largest recent daily jump, long the rest (BTC-hedged): automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: cross_section. Fixed parameters (chosen before any data was read): `{"window": 30, "horizon": 7}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-20-34c60f55`; planned Lab-wide trials: 98.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 3 |
| validation | pre | REJECT | 2/9 | n/a | n/a | 98 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`120955669f9248a0`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0281 (t=2.0, ICIR 0.08): the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | warn | bucket returns are not monotone (25% adjacent increases, rank corr -0.90): profit may sit in one extreme |
| `long_short_legs` | info | the top-minus-bottom spread is not positive; no profit to split |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | fail | **FAILED.**  real spread Sharpe -0.090/period is not above permuted-score placebos (p=1.000): the spread does not earn |
| `selection_vs_timing` | info | spread -0.9523%/period; selection effect -0.9038%; with dates shuffled 0.0595% (a time-invariant tilt or market timing, not stock selection) |
| `market_impact` | fail | **FAILED.**  at AUM 5e+04: gross -74.59%, impact 14.57%, net -90.01% per year |
| `participation_limit` | pass | participation p95 0.83%, max 15.10% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 18% of short exposure in the least liquid 20%; borrow 2.97%/yr vs short-leg profit -125.46%/yr |
| `turnover_vs_decay` | info | holding 16.4 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min -86.88%, median -47.97%, max -31.50% (k=21) |
| `factor_exposure` | info | factors explain 59% of return variance; strongest: low_vol (beta +0.67, t +19.4), reversal (beta +0.11, t +3.8) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? no significant residual alpha (t -1.2) |
| `factor_spanning` | warn | adds nothing the factors do not have (max Sharpe 1.38 -> 1.43) |
| `hidden_short_volatility` | warn | short-option payoff signs: skew -6.6, excess kurtosis 159.6 |
| `market_timing_beta` | info | up beta -0.46, down beta -0.11 (timing t -1.6) |
| `crowding` | info | correlation with momentum -0.01, low_vol +0.76; mean return on momentum crash days -0.0026 |
| `known_anomaly_match` | info | closest known factor: low_vol (corr +0.76) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = -2.22, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; Sharpe -0.69 is not positive, so no length of history separates it from luck |
| `drawdown_plausibility` | warn | max drawdown 100.0% vs 99.6%..100.0% for iid returns with the same mean and volatility: deeper than iid returns produce (fat tails or regime risk) |
| `haircut_sharpe` | info | Sharpe -0.69 becomes -0.00 after Bonferroni for 98 trials (haircut 100%) |
| `neutrality` | warn | mean rolling beta -0.36, mean net exposure -0.09: declared neutral but is not |
| `concentration` | warn | median effective positions 6.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.89 (max 2.00), net -0.09; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Rates (-40.2% vs market -55.3%) |
| `tail_risk` | info | VaR95 -5.87%, CVaR95 -11.61%, CVaR99 -24.25%, worst bar -101.35%, longest recovery 2662 bars |
| `universe_subsampling` | fail | **FAILED.**  0% of 100 random 70% subsets earn a positive net return (median Sharpe -0.63); top-5 symbols give no share of the profit (there is no gross profit): the result does not hold on most subsets |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges -51.46% to -36.74% |
| `cpcv_paths` | warn | net Sharpe over 15 test combinations: min -1.04, median -0.83, 0% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe -0.69 vs -0.08 median on 100 synthetic markets (p = 0.960): not distinguishable from the market-only null |
| `noise_injection` | skip | net Sharpe -0.69 is not positive: nothing to degrade |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **REJECT**, ARL **2/9**. ARL 2/9 — blocked at 3: it earns after costs (market_impact)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| -0.81 | -0.90 | -0.74 | -0.77 | -0.07 | 0.01 | -1.52 | 0.00 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 1.95 | 0.42 | 2.20 |
| 2018 | -0.61 | -0.43 | -0.73 |
| 2019 | -0.48 | -0.15 | 0.94 |
| 2020 | 0.88 | 0.23 | 3.02 |
| 2021 | -1.32 | -0.61 | 0.60 |
| 2022 | -1.03 | -0.18 | -0.64 |
| 2023 | 0.55 | 0.09 | 1.56 |
| 2024 | -1.01 | -0.27 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
