# Search candidate 30e0e5e4: voltrend {'lookback': 14, 'volume_window': 60} sign 1, top 60 liquid coins: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: search_voltrend. Fixed parameters (chosen before any data was read): `{}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-24-7d1a89dc`; planned Lab-wide trials: 104.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 1 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | n/a | n/a | 134 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`cc119d8ebb74a8c0`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0112 (t=1.1): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 19; no exponential decay found (IC does not fall with horizon) |
| `quantile_monotonicity` | pass | returns rise across 5 buckets (rank corr 1.00, spread 1.4247% per period) |
| `long_short_legs` | pass | short leg earns 41% of the spread; long leg 59% |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | pass | real spread Sharpe 0.154/period beats permuted-score placebos (p=0.005) |
| `selection_vs_timing` | info | spread 1.4247%/period; selection effect 1.4586%; with dates shuffled 0.2121% (a time-invariant tilt or market timing, not stock selection) |
| `cost_sensitivity` | warn | the edge does not survive doubled costs: net return +13.4% a year at the modelled costs, -27.4% at double (commission 1 bp and square-root impact at AUM 5e+04) |
| `market_impact` | warn | at AUM 5e+04: gross 78.42%, impact 56.03%, net 19.37% per year |
| `participation_limit` | pass | participation p95 1.70%, max 4858.30% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 7% of short exposure in the least liquid 20%; borrow 2.93%/yr vs short-leg profit -20.09%/yr |
| `turnover_vs_decay` | info | holding 4.6 bars |
| `rebalance_timing_luck` | warn | annual net return by rebalance day: min -15.40%, median 22.70%, max 45.28% (k=21) |
| `factor_exposure` | info | factors explain 19% of return variance; strongest: reversal (beta -0.47, t -14.0), size (beta -0.15, t -3.5) |
| `residual_alpha` | pass | Is the return still there after market, size, momentum, reversal and low-volatility exposures? residual alpha t 4.5 clears the 3.0 hurdle |
| `factor_spanning` | info | max Sharpe rises 1.68 -> 2.30 (+0.61) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 0.4) |
| `market_timing_beta` | info | up beta -0.05, down beta -0.04 (timing t -0.2) |
| `crowding` | info | correlation with momentum -0.07, low_vol -0.05; mean return on momentum crash days +0.0097 |
| `known_anomaly_match` | info | closest known factor: reversal (corr -0.42) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = 0.73, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | fail | **FAILED.** How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; about 181.8 years needed to separate Sharpe 0.23 from the best of 134 luck-only variants |
| `drawdown_plausibility` | pass | max drawdown 93.1% vs 68.2%..99.7% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe 0.23 becomes 0.00 after Bonferroni for 134 trials (haircut 100%) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.030 over 134 trial(s) on net returns (Sharpe 0.23 a year after commission 1 bp and square-root impact at AUM 5e+04) |
| `neutrality` | pass | mean rolling beta -0.05, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 23.0, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.91 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Crypto winter (-11.0% vs market -59.2%) |
| `tail_risk` | info | VaR95 -4.73%, CVaR95 -7.69%, CVaR99 -13.69%, worst bar -22.60%, longest recovery 423 bars |
| `universe_subsampling` | pass | 100% of 100 random 70% subsets earn a positive net return (median Sharpe 0.73); top-5 symbols give 60% of the profit |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges 43.26% to 66.66% |
| `cpcv_paths` | info | net Sharpe over 15 test combinations: min 0.54, median 0.97, 100% positive |
| `synthetic_market_null` | pass | The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe 0.94 vs 0.06 median on 100 synthetic markets (p = 0.020) |
| `noise_injection` | pass | net Sharpe 0.94 -> 0.9117 at 0.1x, 0.8551 at 0.25x, 0.7228 at 0.5x |
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
| 0.38 | 0.00 | 0.27 | -0.28 | -0.01 | 0.00 | 0.77 | 0.03 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | -0.13 | -0.06 | 2.20 |
| 2018 | 2.75 | 2.64 | -0.73 |
| 2019 | -0.08 | -0.04 | 0.94 |
| 2020 | 2.56 | 0.77 | 3.02 |
| 2021 | 0.97 | 0.28 | 0.60 |
| 2022 | -0.43 | -0.10 | -0.64 |
| 2023 | -0.14 | -0.03 | 1.56 |
| 2024 | 0.70 | 0.13 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
