# Search candidate d17472fd: strev {'lookback': 5, 'mode': 'volnorm'} sign 1, top 60 liquid coins: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_strev. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-48-6b8bffcd`; planned Lab-wide trials: 134.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 1 |
| validation | pre | REJECT | 2/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`b67bae3acde13007`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0244 (t=2.6, ICIR 0.10): the signal predicts returns |
| `ic_decay` | info | best horizon 13; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 2.3964% per period) |
| `long_short_legs` | pass | short leg earns 52% of the spread; long leg 48% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.173/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 2.3964%/period; selection effect 2.4138%; with dates shuffled 0.3704% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | fail | **FAILED.**  the portfolio does not earn after costs: net return -2.0% a year at the modelled costs, -71.2% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | fail | **FAILED.**  at AUM 5e+04: gross 97.31%, impact 95.23%, net -2.94% per year |
| `participation_limit` | pass | participation p95 1.82%, max 9913.00% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | pass | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 8% of short exposure in the least liquid 20%; borrow 2.95%/yr vs short-leg profit 11.01%/yr |
| `turnover_vs_decay` | info | holding 2.8 bars |
| `rebalance_timing_luck` | warn | annual net return by rebalance day: min -12.77%, median 14.01%, max 60.94% (k=21) |
| `factor_exposure` | info | factors explain 36% of return variance; strongest: reversal (beta -0.64, t -19.5), size (beta -0.09, t -2.8) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 6.6 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.76 (+1.08) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.6) |
| `market_timing_beta` | info | up beta 0.02, down beta -0.03 (timing t 0.9) |
| `crowding` | info | correlation with momentum -0.08, low_vol -0.06; mean return on momentum crash days +0.0173 |
| `known_anomaly_match` | info | closest known factor: reversal (corr -0.59) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = -0.12, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; Sharpe -0.04 is not positive, so no length of history separates it from luck |
| `drawdown_plausibility` | pass | max drawdown 98.3% vs 75.6%..99.9% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe -0.04 becomes -0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.003 over 134 trial(s) on net returns (Sharpe -0.04 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.03, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 24.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.92 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Rates (-26.1% vs market -64.2%) |
| `tail_risk` | info | VaR95 -4.49%, CVaR95 -7.20%, CVaR99 -12.23%, worst bar -28.76%, longest recovery 674 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.98); top-5 symbols give 41% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 65.26% to 78.85% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.64, median 1.21, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 1.24 vs 0.06 median on 100 synthetic markets (p = 0.010) |
| `noise_injection` | pass | net Sharpe 1.24 -> 1.1802 at 0.1x, 1.1553 at 0.25x, 1.0102 at 0.5x |
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
| 0.73 | 0.46 | 0.67 | -0.29 | 0.04 | 0.00 | 1.40 | 0.12 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | -0.33 | -0.08 | 2.20 |
| 2018 | 2.42 | 1.16 | -0.73 |
| 2019 | 0.74 | 0.13 | 0.94 |
| 2020 | 0.76 | 0.14 | 3.02 |
| 2021 | 1.88 | 0.62 | 0.60 |
| 2022 | -0.17 | -0.05 | -0.64 |
| 2023 | -0.14 | -0.03 | 1.56 |
| 2024 | 0.63 | 0.11 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
