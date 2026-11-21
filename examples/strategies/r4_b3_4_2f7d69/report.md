# Search candidate 2f7d69bd: hi52 {'window': 365, 'skip': 7} sign 1, top 30 liquid coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_hi52. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-42-bcc6bbf0`; planned Lab-wide trials: 124.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | NEEDS_MORE_EVIDENCE | 4/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 4/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`1d22a24c28ceffc5`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | info | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0651 (t=4.3, ICIR 0.19): the signal predicts returns |
| `ic_decay` | info | best horizon 20; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 0.70, spread 0.7770% per period) |
| `long_short_legs` | warn | 88% of the spread profit comes from the short leg: shorts are often not implementable (borrow, bans, microcaps) |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.085/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 0.7770%/period; selection effect 0.7804%; with dates shuffled 0.6608% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | warn | the edge does not survive doubled costs: net return +0.1% a year at the modelled costs, -8.6% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | warn | at AUM 5e+04: gross 12.82%, impact 11.51%, net 0.14% per year |
| `participation_limit` | pass | participation p95 0.26%, max 17.75% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 0% of short exposure in the least liquid 20%; borrow 2.59%/yr vs short-leg profit -25.18%/yr |
| `turnover_vs_decay` | info | holding 10.3 bars |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min -9.17%, median 11.21%, max 22.63% (k=21) |
| `factor_exposure` | info | factors explain 13% of return variance; strongest: market (beta -0.26, t -7.0), momentum (beta +0.19, t +3.7) |
| `residual_alpha` | warn | Is the return still there after market, size, momentum, reversal and low-volatility exposures? no significant residual alpha (t 1.1) |
| `factor_spanning` | warn | adds nothing the factors do not have (max Sharpe 1.68 -> 1.73) |
| `hidden_short_volatility` | warn | short-option payoff signs: negative convexity to the market |
| `market_timing_beta` | info | up beta -0.30, down beta -0.21 (timing t -1.1) |
| `crowding` | info | correlation with momentum +0.16, low_vol +0.12; mean return on momentum crash days -0.0105 |
| `known_anomaly_match` | info | closest known factor: market (corr -0.33) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 0.01, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 2788936.0 years needed to separate Sharpe 0.00 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 94.1% vs 71.8%..99.8% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.00 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.004 over 134 trial(s) on net returns (Sharpe 0.00 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.26, mean net exposure -0.08 |
| `concentration` | warn | median effective positions 8.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.65 (max 2.00), net -0.08; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Rates (-71.1% vs market -64.2%) |
| `tail_risk` | info | VaR95 -4.98%, CVaR95 -8.30%, CVaR99 -14.04%, worst bar -28.05%, longest recovery 2207 bars |
| `universe_subsampling` | warn | 50% of 100 random 70% subsets earn a positive net return (median Sharpe 0.00); top-5 symbols give 371% of the profit: the edge leans on a few names |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | warn | annual return over 13 start dates ranges -0.74% to 10.10%: a later start loses while the full sample wins |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min -0.24, median 0.14, 80% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.17 vs 0.16 median on 100 synthetic markets (p = 0.505): not distinguishable from the market-only null |
| `noise_injection` | pass | net Sharpe 0.17 -> 0.176 at 0.1x, 0.1441 at 0.25x, 0.1011 at 0.5x |
| `data_source_replication` | skip | no second price source given |
| `bar_construction` | skip | daily or slower bars: the bar grid is the calendar day |
| `universe_lookahead` | pass | every held symbol is inside its membership window |
| `classification_lookahead` | skip | no groups file given |
| `cross_market_close_alignment` | skip | no exchange or close-time map given |
| `post_discovery_decay` | skip | no discovery date given |
| `research_hygiene` | skip | no research-process information given |

Verdict **NEEDS_MORE_EVIDENCE**, ARL **4/9**. ARL 4/9 — blocked at 5: it is new alpha (hidden_short_volatility, residual_alpha)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.62 | 0.49 | 0.62 | -0.47 | 0.19 | 0.03 | 0.96 | 0.08 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | n/a | 0.00 | 2.20 |
| 2018 | -0.91 | -0.19 | -0.73 |
| 2019 | 2.19 | 0.77 | 0.94 |
| 2020 | 3.10 | 0.86 | 3.02 |
| 2021 | 1.45 | 0.53 | 0.60 |
| 2022 | -1.58 | -0.31 | -0.64 |
| 2023 | 0.86 | 0.15 | 1.56 |
| 2024 | 1.43 | 0.34 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
