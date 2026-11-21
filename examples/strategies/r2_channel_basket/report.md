# Donchian channel position basket, 18 coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: trend_basket. Fixed parameters (chosen before any data was read): `{"window": 55, "horizon": 7}`. Costs: Binance taker fees (VIP0: spot 10 bps, perpetual 5 bps) + 2-12 bps spread/slippage per coin, fills on the next bar; also doubled.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-6-04691687`; planned Lab-wide trials: 83.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 6/9 | n/a | n/a | 3 |
| validation | pre | PASS_WITH_WARNINGS | 6/9 | n/a | n/a | 83 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`950053bf666b414a`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0416 (t=3.0, ICIR 0.12): the signal predicts returns |
| `ic_decay` | info | best horizon 15; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 0.90, spread 1.8862% per period) |
| `long_short_legs` | pass | short leg earns 48% of the spread; long leg 52% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.176/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.8862%/period; selection effect 1.9543%; with dates shuffled 0.0692% (a time-invariant tilt or market timing, not stock selection) |
| `market_impact` | pass | at AUM 5e+04: gross 130.89%, impact 42.33%, net 85.35% per year |
| `participation_limit` | pass | participation p95 0.58%, max 20.43% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 5.18e+05 and reaches zero at 5.18e+05 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 32% of short exposure in the least liquid 20%; borrow 2.94%/yr vs short-leg profit -17.32%/yr |
| `turnover_vs_decay` | info | holding 4.4 bars |
| `rebalance_timing_luck` | warn | annual net return by rebalance day: min -4.75%, median 33.84%, max 73.82% (k=21) |
| `factor_exposure` | info | factors explain 34% of return variance; strongest: reversal (beta -0.45, t -12.2), low_vol (beta -0.23, t -6.3) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 4.4 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.38 -> 1.84 (+0.46) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 1.6) |
| `market_timing_beta` | info | up beta 0.08, down beta -0.01 (timing t 1.1) |
| `crowding` | info | correlation with momentum +0.07, low_vol -0.15; mean return on momentum crash days +0.0022 |
| `known_anomaly_match` | info | closest known factor: reversal (corr -0.50) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | pass | t = 4.78 clears the Harvey-Liu-Zhu hurdle of 3.0 |
| `min_backtest_length` | pass | How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 4.3 years needed to separate Sharpe 1.44 from the best of 83 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 60.0% vs 48.6%..86.5% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 1.44 becomes 1.14 after Bonferroni for 83 trials (haircut 21%) |
| `neutrality` | pass | mean rolling beta -0.02, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 6.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.92 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Covid (-9.7% vs market -48.0%) |
| `tail_risk` | info | VaR95 -4.74%, CVaR95 -8.00%, CVaR99 -13.58%, worst bar -23.75%, longest recovery 252 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 1.17); top-5 symbols give 69% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 80.19% to 100.00% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.67, median 1.50, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 1.44 vs 0.07 median on 100 synthetic markets (p = 0.010) |
| `noise_injection` | pass | net Sharpe 1.44 -> 1.493 at 0.1x, 1.4571 at 0.25x, 1.333 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **PASS_WITH_WARNINGS**, ARL **6/9**. ARL 6/9 — blocked at 7: tradable and robust (rebalance_timing_luck)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 1.57 | 1.54 | 14.61 | -0.40 | 0.60 | 0.36 | 2.75 | 0.74 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 4.61 | 0.88 | 2.20 |
| 2018 | -0.54 | -0.22 | -0.73 |
| 2019 | 0.89 | 0.31 | 0.94 |
| 2020 | 1.42 | 0.80 | 3.02 |
| 2021 | 2.90 | 6.67 | 0.60 |
| 2022 | -0.64 | -0.19 | -0.64 |
| 2023 | 1.49 | 0.60 | 1.56 |
| 2024 | 1.18 | 0.57 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
