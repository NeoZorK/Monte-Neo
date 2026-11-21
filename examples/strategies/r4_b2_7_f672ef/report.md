# Search candidate f672efd5: strev {'lookback': 5, 'mode': 'volnorm'} sign 1, top 30 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_strev. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-35-2a6f68ce`; planned Lab-wide trials: 114.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 5/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`54a451f147fa03bd`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0294 (t=3.0, ICIR 0.10): the signal predicts returns |
| `ic_decay` | info | best horizon 19; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 0.90, spread 1.7816% per period) |
| `long_short_legs` | pass | short leg earns 53% of the spread; long leg 47% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.183/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.7816%/period; selection effect 1.7826%; with dates shuffled 0.2255% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | warn | the edge does not survive doubled costs: net return +17.6% a year at the modelled costs, -39.8% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | warn | at AUM 5e+04: gross 108.82%, impact 78.18%, net 25.58% per year |
| `participation_limit` | pass | participation p95 1.05%, max 28.41% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | pass | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 6% of short exposure in the least liquid 20%; borrow 2.95%/yr vs short-leg profit 13.99%/yr |
| `turnover_vs_decay` | info | holding 2.8 bars |
| `rebalance_timing_luck` | warn | annual net return by rebalance day: min -22.17%, median 28.38%, max 69.03% (k=21) |
| `factor_exposure` | info | factors explain 24% of return variance; strongest: reversal (beta -0.61, t -16.2), market (beta +0.06, t +2.5) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 5.6 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.49 (+0.80) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.4) |
| `market_timing_beta` | info | up beta 0.05, down beta -0.08 (timing t 2.3) |
| `crowding` | info | correlation with momentum -0.05, low_vol +0.02; mean return on momentum crash days +0.0145 |
| `known_anomaly_match` | info | closest known factor: reversal (corr -0.48) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 0.95, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 111.9 years needed to separate Sharpe 0.30 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 94.4% vs 67.3%..99.7% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.30 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.048 over 134 trial(s) on net returns (Sharpe 0.30 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.06, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 12.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.92 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Volmageddon (-21.3% vs market -0.3%) |
| `tail_risk` | info | VaR95 -5.10%, CVaR95 -7.88%, CVaR99 -13.37%, worst bar -28.76%, longest recovery 362 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 1.02); top-5 symbols give 43% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 74.59% to 87.21% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.66, median 1.25, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 1.26 vs 0.00 median on 100 synthetic markets (p = 0.010) |
| `noise_injection` | pass | net Sharpe 1.26 -> 1.2538 at 0.1x, 1.2737 at 0.25x, 1.1605 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **NEEDS_MORE_EVIDENCE**, ARL **5/9**. ARL 5/9 — blocked at 6: it survives the search (deflated_sharpe, min_backtest_length)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.48 | 0.04 | 0.41 | -0.48 | -0.02 | 0.00 | 1.00 | 0.05 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 3.23 | 0.59 | 2.20 |
| 2018 | 3.30 | 1.87 | -0.73 |
| 2019 | 0.02 | -0.02 | 0.94 |
| 2020 | 2.35 | 0.90 | 3.02 |
| 2021 | 2.47 | 1.00 | 0.60 |
| 2022 | -0.41 | -0.11 | -0.64 |
| 2023 | -1.20 | -0.19 | 1.56 |
| 2024 | 0.01 | -0.02 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
