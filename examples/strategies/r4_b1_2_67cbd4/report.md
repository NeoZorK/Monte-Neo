# Search candidate 67cbd439: bab {'window': 30} sign -1, top 30 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_bab. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-22-d1e83f8b`; planned Lab-wide trials: 104.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 1 |
| validation | pre | REJECT | 2/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`d2fea8938b9ea7d1`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0490 (t=3.6, ICIR 0.15): the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | warn | bucket returns are not monotone (75% adjacent increases, rank corr 0.70): profit may sit in one extreme |
| `long_short_legs` | pass | short leg earns 64% of the spread; long leg 36% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.062/period beats permuted-score placebos (p=0.015) |
| `selection_vs_timing` | info | spread 0.6081%/period; selection effect 0.5816%; with dates shuffled 0.4506% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | fail | **FAILED.**  the portfolio does not earn after costs: net return -23.8% a year at the modelled costs, -39.1% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | fail | **FAILED.**  at AUM 5e+04: gross -12.41%, impact 20.74%, net -34.55% per year |
| `participation_limit` | pass | participation p95 1.03%, max 13.61% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 5% of short exposure in the least liquid 20%; borrow 2.95%/yr vs short-leg profit -41.37%/yr |
| `turnover_vs_decay` | info | holding 10.0 bars |
| `rebalance_timing_luck` | warn | annual net return by rebalance day: min -23.75%, median -1.14%, max 26.61% (k=21) |
| `factor_exposure` | info | factors explain 15% of return variance; strongest: market (beta -0.18, t -6.6), size (beta +0.22, t +4.0) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? no significant residual alpha (t -0.2) |
| `factor_spanning` | warn | adds nothing the factors do not have (max Sharpe 1.68 -> 1.69) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew -0.1) |
| `market_timing_beta` | info | up beta -0.27, down beta -0.24 (timing t -0.3) |
| `crowding` | info | correlation with momentum +0.01, low_vol +0.28; mean return on momentum crash days +0.0052 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.33) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = -1.22, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; Sharpe -0.39 is not positive, so no length of history separates it from luck |
| `drawdown_plausibility` | pass | max drawdown 99.4% vs 92.8%..100.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe -0.39 becomes -0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.000 over 134 trial(s) on net returns (Sharpe -0.39 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | warn | mean rolling beta -0.32, mean net exposure -0.04: declared neutral but is not |
| `concentration` | warn | median effective positions 12.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.92 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: SVB (-14.9% vs market 6.7%) |
| `tail_risk` | info | VaR95 -5.76%, CVaR95 -9.28%, CVaR99 -16.56%, worst bar -51.77%, longest recovery 2644 bars |
| `universe_subsampling` | warn | 54% of 100 random 70% subsets earn a positive net return (median Sharpe 0.01); top-5 symbols give no share of the profit (there is no gross profit): the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | warn | annual return over 13 start dates ranges -8.56% to 9.75%: the range exceeds the median absolute return |
| `cpcv_paths` | warn | net Sharpe over 15 test combinations: min -0.82, median -0.38, 33% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe -0.14 vs 0.20 median on 100 synthetic markets (p = 0.861): not distinguishable from the market-only null |
| `noise_injection` | skip | net Sharpe -0.14 is not positive: nothing to degrade |
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
| 0.86 | 0.69 | 1.04 | -0.29 | 0.21 | 0.05 | 1.42 | 0.18 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 2.17 | 0.41 | 2.20 |
| 2018 | 0.17 | -0.01 | -0.73 |
| 2019 | 2.22 | 0.59 | 0.94 |
| 2020 | 1.78 | 0.63 | 3.02 |
| 2021 | 1.16 | 0.35 | 0.60 |
| 2022 | 0.48 | 0.08 | -0.64 |
| 2023 | 0.79 | 0.15 | 1.56 |
| 2024 | 0.92 | 0.21 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
