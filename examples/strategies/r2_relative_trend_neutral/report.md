# Trend versus market: long-short on distance above SMA relative to BTC: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: market_neutral. Fixed parameters (chosen before any data was read): `{"sma": 100, "horizon": 7}`. Costs: Binance taker fees (VIP0: spot 10 bps, perpetual 5 bps) + 2-12 bps spread/slippage per coin, fills on the next bar; also doubled.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-8-d56e3029`; planned Lab-wide trials: 83.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 3 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 83 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`8a50391c4b74192c`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0145 (t=0.9): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 19; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 0.90, spread 1.4696% per period) |
| `long_short_legs` | pass | short leg earns 48% of the spread; long leg 52% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.124/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.4696%/period; selection effect 1.4048%; with dates shuffled 0.2345% (a time-invariant tilt or market timing, not stock selection) |
| `market_impact` | pass | at AUM 5e+04: gross 76.01%, impact 16.94%, net 57.84% per year |
| `participation_limit` | pass | participation p95 0.54%, max 17.08% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 5.18e+05 and reaches zero at 1.18e+06 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 33% of short exposure in the least liquid 20%; borrow 2.89%/yr vs short-leg profit -47.45%/yr |
| `turnover_vs_decay` | info | holding 10.9 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 26.31%, median 47.84%, max 88.12% (k=21) |
| `factor_exposure` | info | factors explain 33% of return variance; strongest: low_vol (beta -0.47, t -10.6), reversal (beta -0.35, t -10.2) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 3.0 is below the Harvey-Liu-Zhu hurdle of 3.0 |
| `factor_spanning` | info | max Sharpe rises 1.38 -> 1.64 (+0.26) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.9) |
| `market_timing_beta` | info | up beta 0.02, down beta -0.08 (timing t 1.2) |
| `crowding` | info | correlation with momentum +0.17, low_vol -0.31; mean return on momentum crash days -0.0128 |
| `known_anomaly_match` | info | closest known factor: reversal (corr -0.32) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | warn | t = 2.41 is above 2 but below the Harvey-Liu-Zhu hurdle of 3.0 |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 15.6 years needed to separate Sharpe 0.75 from the best of 83 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 78.3% vs 64.5%..98.6% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.75 becomes 0.00 after Bonferroni for 83 trials (haircut 100%) |
| `neutrality` | pass | mean rolling beta -0.07, mean net exposure -0.09 |
| `concentration` | warn | median effective positions 6.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.84 (max 2.00), net -0.09; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Covid (-28.4% vs market -48.0%) |
| `tail_risk` | info | VaR95 -5.95%, CVaR95 -9.59%, CVaR99 -15.69%, worst bar -33.03%, longest recovery 549 bars |
| `universe_subsampling` | warn | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.82); top-5 symbols give 94% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 40.08% to 65.45% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.14, median 0.69, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.75 vs 0.09 median on 100 synthetic markets (p = 0.020) |
| `noise_injection` | pass | net Sharpe 0.75 -> 0.7666 at 0.1x, 0.8036 at 0.25x, 0.7675 at 0.5x |
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
| 1.01 | 0.93 | 1.94 | -0.29 | 0.04 | 0.00 | 1.96 | 0.32 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 0.82 | 0.10 | 2.20 |
| 2018 | 1.25 | 0.50 | -0.73 |
| 2019 | 1.24 | 0.36 | 0.94 |
| 2020 | 1.05 | 0.25 | 3.02 |
| 2021 | 2.19 | 1.72 | 0.60 |
| 2022 | -0.55 | -0.11 | -0.64 |
| 2023 | 1.17 | 0.22 | 1.56 |
| 2024 | 0.10 | -0.01 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
