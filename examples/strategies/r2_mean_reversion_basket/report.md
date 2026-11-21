# Short-term mean reversion basket, long-short, 18 coins: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: mean_reversion. Fixed parameters (chosen before any data was read): `{"lookback": 5, "horizon": 3}`. Costs: Binance taker fees (VIP0: spot 10 bps, perpetual 5 bps) + 2-12 bps spread/slippage per coin, fills on the next bar; also doubled.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-7-0298fd67`; planned Lab-wide trials: 83.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | n/a | n/a | 3 |
| validation | pre | REJECT | 2/9 | n/a | n/a | 83 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`a8fa226468fea695`, pre data)

| Check | Status | What it means |
|---|---|---|
| `ic` | warn | Information coefficient: does the score rank the next returns better than chance (t-statistic)? mean rank IC 0.0054 (t=0.6): no evidence the signal predicts returns |
| `ic_decay` | info | best horizon 1; IC half-life 1.1 bars |
| `quantile_monotonicity` | warn | bucket returns are not monotone (25% adjacent increases, rank corr -0.90): profit may sit in one extreme |
| `long_short_legs` | info | the top-minus-bottom spread is not positive; no profit to split |
| `breadth_consistency` | skip | no claimed IR given (--claim-ir) |
| `signal_placebo` | fail | **FAILED.**  real spread Sharpe -0.090/period is not above permuted-score placebos (p=1.000): the spread does not earn |
| `selection_vs_timing` | info | spread -0.7218%/period; selection effect -0.7341%; with dates shuffled -0.0155% (a time-invariant tilt or market timing, not stock selection) |
| `market_impact` | fail | **FAILED.**  at AUM 5e+04: gross -121.53%, impact 81.17%, net -207.97% per year |
| `participation_limit` | pass | participation p95 0.77%, max 39.25% of bar volume (limit 5%) |
| `capacity_curve` | info | net Sharpe is not positive even at the smallest AUM |
| `short_feasibility` | warn | Short legs on spot coins need borrow or perpetuals; the check flags shorts that cannot be implemented as stated. 19% of short exposure in the least liquid 20%; borrow 2.99%/yr vs short-leg profit -158.25%/yr |
| `turnover_vs_decay` | info | holding 2.7 bars, signal half-life 1.1 bars: you hold 2.5x longer than the signal lasts |
| `rebalance_timing_luck` | pass | annual net return by rebalance day: min -146.93%, median -63.88%, max -19.34% (k=21) |
| `factor_exposure` | info | factors explain 95% of return variance; strongest: reversal (beta +0.86, t +82.0), low_vol (beta -0.09, t -6.2) |
| `residual_alpha` | fail | **FAILED.** Is the return still there after market, size, momentum, reversal and low-volatility exposures? 0% of the return is explained by reversal and low_vol: repackaged factors (alpha t -0.2) |
| `factor_spanning` | warn | adds nothing the factors do not have (max Sharpe 1.38 -> 1.38) |
| `hidden_short_volatility` | pass | no short-volatility payoff (skew 10.0) |
| `market_timing_beta` | info | up beta 0.19, down beta 0.05 (timing t 0.4) |
| `crowding` | info | correlation with momentum +0.04, low_vol -0.34; mean return on momentum crash days -0.0161 |
| `known_anomaly_match` | info | closest known factor: reversal (corr +0.97) |
| `book_correlation` | skip | no book given (--book): the value to an existing book was not assessed |
| `hlz_hurdle` | info | t = -3.56, below 2 (the no-edge check owns this case) |
| `min_backtest_length` | warn | How many years of history the Sharpe needs after the number of trials (cross-sectional score). 7.4 years of history; Sharpe -1.07 is not positive, so no length of history separates it from luck |
| `drawdown_plausibility` | pass | max drawdown 100.0% vs 100.0%..100.0% for iid returns with the same mean and volatility |
| `haircut_sharpe` | info | Sharpe -1.07 becomes -0.63 after Bonferroni for 83 trials (haircut 41%) |
| `neutrality` | pass | mean rolling beta 0.00, mean net exposure -0.04 |
| `concentration` | warn | median effective positions 6.9, largest single weight 100% |
| `leverage_gross_net` | info | gross 1.95 (max 2.00), net -0.04; largest gross jump 1.00 |
| `historical_stress_replay` | info | 6 stress windows in the data; worst for the strategy: Crypto winter (-20.7% vs market -56.3%) |
| `tail_risk` | info | VaR95 -6.41%, CVaR95 -11.48%, CVaR99 -20.89%, worst bar -37.33%, longest recovery 2664 bars |
| `universe_subsampling` | fail | **FAILED.**  0% of 100 random 70% subsets earn a positive net return (median Sharpe -0.94); top-5 symbols give no share of the profit (there is no gross profit): the result does not hold on most subsets |
| `group_split` | skip | no groups given (sector/country per symbol) |
| `start_date_sensitivity` | pass | annual return over 13 start dates ranges -83.85% to -46.00% |
| `cpcv_paths` | warn | net Sharpe over 15 test combinations: min -2.14, median -0.82, 0% positive |
| `synthetic_market_null` | fail | **FAILED.** The score is re-run on bootstrapped markets where it has no link to returns; it must not earn there. net Sharpe -1.07 vs -0.08 median on 100 synthetic markets (p = 1.000): not distinguishable from the market-only null |
| `noise_injection` | skip | net Sharpe -1.07 is not positive: nothing to degrade |
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
| -2.32 | -2.92 | -0.91 | -0.91 | -0.06 | 0.00 | -4.56 | 0.00 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | -0.66 | -0.26 | 2.20 |
| 2018 | -1.50 | -0.60 | -0.73 |
| 2019 | -1.99 | -0.41 | 0.94 |
| 2020 | -2.02 | -0.45 | 3.02 |
| 2021 | -2.80 | -0.66 | 0.60 |
| 2022 | -2.52 | -0.37 | -0.64 |
| 2023 | -1.92 | -0.29 | 1.56 |
| 2024 | -2.22 | -0.38 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
