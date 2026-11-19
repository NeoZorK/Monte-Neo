# Funding crowding: short coins with the highest trailing perpetual funding, long the lowest (BTC-hedged): automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: carry_signal. Fixed parameters (chosen before any data was read): `{"lookback": 14, "horizon": 7}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-17-b6c791a3`; planned Lab-wide trials: 98.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 3 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 98 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`5d54d965533d5eeb`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0328 (t=2.0): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 5; IC half-life 19.4 bars |
| `quantile_monotonicity` | warn | bucket returns are not monotone (75% adjacent increases, rank corr 0.20): profit may sit in one extreme |
| `long_short_legs` | warn | 82% of the spread profit comes from the short leg: shorts are often not implementable (borrow, bans, microcaps) |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.064/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 0.9101%/period; selection effect 0.8573%; with dates shuffled -0.1754% (a time-invariant tilt or market timing, not stock selection) |
| `market_impact` | pass | at AUM 5e+04: gross 61.06%, impact 6.93%, net 53.40% per year |
| `participation_limit` | pass | participation p95 0.27%, max 2.82% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 2.68e+06 and reaches zero at 6.11e+06 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 25% of short exposure in the least liquid 20%; borrow 2.02%/yr vs short-leg profit -46.20%/yr |
| `turnover_vs_decay` | info | holding 13.5 bars, signal half-life 19.4 bars: you trade 1.4x more than the signal needs |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min -27.27%, median -4.59%, max 9.99% (k=21) |
| `factor_exposure` | info | factors explain 44% of return variance; strongest: size (beta +0.36, t +3.8), market (beta -0.18, t -3.6) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? no significant residual alpha (t 1.9) |
| `factor_spanning` | info | max Sharpe rises 1.25 -> 1.37 (+0.12) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 21.3) |
| `market_timing_beta` | info | up beta 0.52, down beta -0.21 (timing t 1.3) |
| `crowding` | info | correlation with momentum +0.04, low_vol -0.52; mean return on momentum crash days +0.0067 |
| `known_anomaly_match` | info | closest known factor: size (corr +0.58) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 1.73, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 31.7 years needed to separate Sharpe 0.54 from the best of 98 luck-only variants |
| `drawdown_plausibility` | warn | max drawdown 65.4% vs 73.6%..99.8% for iid returns with the same mean and volatility: too smooth for its volatility (smoothing, stale prices or overfitting) |
| `haircut_sharpe` | info | Sharpe 0.54 becomes 0.00 after Bonferroni for 98 trials (haircut 100%) |
| `neutrality` | pass | mean rolling beta 0.00, mean net exposure -0.00 |
| `concentration` | warn | median effective positions 4.8, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.34 (max 2.00), net -0.00; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Rates (-20.5% vs market -58.5%) |
| `tail_risk` | info | VaR95 -4.31%, CVaR95 -7.14%, CVaR99 -12.82%, worst bar -37.60%, longest recovery 1345 bars |
| `universe_subsampling` | warn | 88% of 100 random 70% subsets earn a positive net return (median Sharpe 0.35); top-5 symbols give 130% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 42.13% to 60.05% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.35, median 0.39, 67% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.54 vs 0.07 median on 100 synthetic markets (p = 0.059) |
| `noise_injection` | pass | net Sharpe 0.54 -> 0.4407 at 0.1x, 0.3684 at 0.25x, 0.3428 at 0.5x |
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
| 0.78 | 0.70 | 1.60 | -0.45 | -0.01 | 0.00 | 1.58 | 0.13 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | n/a | 0.00 | -0.73 |
| 2019 | n/a | 0.00 | 0.94 |
| 2020 | -0.11 | -0.07 | 3.02 |
| 2021 | 2.04 | 2.46 | 0.60 |
| 2022 | -0.67 | -0.15 | -0.64 |
| 2023 | 0.21 | 0.02 | 1.56 |
| 2024 | -0.63 | -0.14 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
