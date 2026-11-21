# Search candidate 0ea5fa19: comp_VHZ {'parts': ['V', 'H', 'Z']} sign 1, top 30 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_comp_VHZ. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-55-5af76e71`; planned Lab-wide trials: 134.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 3/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`45785f0f5c423b00`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC -0.0164 (t=-1.6): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 19; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 0.4360% per period) |
| `long_short_legs` | pass | short leg earns 41% of the spread; long leg 59% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.077/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 0.4360%/period; selection effect 0.4470%; with dates shuffled -0.0412% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | pass | net return +34.3% a year at the modelled costs, +18.8% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | pass | at AUM 5e+04: gross 72.20%, impact 20.56%, net 49.75% per year |
| `participation_limit` | pass | participation p95 0.37%, max 20.88% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe halves at AUM 5.18e+05 and reaches zero at 1.18e+06 |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 0% of short exposure in the least liquid 20%; borrow 2.59%/yr vs short-leg profit -12.77%/yr |
| `turnover_vs_decay` | info | holding 6.4 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min 1.88%, median 22.14%, max 42.32% (k=21) |
| `factor_exposure` | info | factors explain 2% of return variance; strongest: momentum (beta +0.14, t +2.9), reversal (beta -0.07, t -1.8) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 3.4 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.03 (+0.35) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 1.5) |
| `market_timing_beta` | info | up beta -0.08, down beta -0.08 (timing t -0.1) |
| `crowding` | info | correlation with momentum +0.10, low_vol +0.06; mean return on momentum crash days +0.0027 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.11) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | warn | t = 2.13 is above 2 but below the Harvey-Liu-Zhu hurdle of 3.0 |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 21.6 years needed to separate Sharpe 0.67 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 67.8% vs 52.7%..95.6% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.67 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.328 over 134 trial(s) on net returns (Sharpe 0.67 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.09, mean net exposure -0.08 |
| `concentration` | warn | median effective positions 8.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.65 (max 2.00), net -0.08; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Covid (-11.9% vs market -49.0%) |
| `tail_risk` | info | VaR95 -4.13%, CVaR95 -6.34%, CVaR99 -9.92%, worst bar -16.87%, longest recovery 636 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.69); top-5 symbols give 56% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 49.82% to 60.85% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.30, median 0.99, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.98 vs -0.06 median on 100 synthetic markets (p = 0.010) |
| `noise_injection` | pass | net Sharpe 0.98 -> 0.9408 at 0.1x, 0.8865 at 0.25x, 0.8356 at 0.5x |
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
| 0.21 | -0.09 | 0.10 | -0.32 | -0.04 | 0.00 | 0.50 | 0.01 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | 1.34 | 0.38 | -0.73 |
| 2019 | 1.39 | 0.35 | 0.94 |
| 2020 | 2.12 | 0.58 | 3.02 |
| 2021 | 1.15 | 0.40 | 0.60 |
| 2022 | -0.07 | -0.03 | -0.64 |
| 2023 | -0.46 | -0.08 | 1.56 |
| 2024 | -0.54 | -0.12 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
