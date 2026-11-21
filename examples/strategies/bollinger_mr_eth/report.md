# Bollinger band reversion, ETH: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: mean_reversion. Fixed parameters (chosen before any data was read): `{"window": 20, "k": 2.0}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-1-ffbf15ad`; planned Lab-wide trials: 83.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | REJECT | 2/9 | -0.11 | 0.27 | 6 |
| validation | pre | REJECT | 2/9 | 0.07 | 0.01 | 83 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`8e3db1ee7b736ee8`, pre data)

| Check | Status | What it means |
|---|---|---|
| `data_integrity` | pass | The price table is clean (no NaN, inverted bars or duplicates). A broken table makes every other number meaningless. OHLCV is clean |
| `data_quality` | pass | no spikes, frozen prices, split jumps or gaps |
| `determinism` | pass | The same input must give the same signal; otherwise nothing can be rechecked. signal() is deterministic |
| `lookahead_truncation` | pass | Cutting the future off the data must not change past signals. A change means the signal peeks ahead. truncation probe: no leak detected |
| `lookahead_perturbation` | pass | Changing only future prices must not change today's signal. future-perturbation probe: no leak detected |
| `external_data` | pass | outside data: none read (df only) |
| `repaint_history` | pass | A signal shown at bar t must not be rewritten later. repaint (history): the signal of a closed bar never changed (19 prefixes, +50 bars, revised tail) |
| `repaint_live` | info | repaint (forming bar): decided at the close, flickers while the bar forms (22% of snapshots): act on it only after the bar closes |
| `lookahead_static_lint` | pass | Static scan of the source for shift(-1), centred windows and whole-series statistics. static lint: clean |
| `implausible_accuracy` | pass | next-bar hit rate 0.513 over 707 bars (z 0.7) |
| `data_independence` | pass | data independence: positions follow the prices |
| `implausible_performance` | pass | Sharpe or accuracy too good to be true is treated as a bug until proven otherwise. annualized Sharpe 0.1 is within the usual range |
| `costs_modeled` | pass | Commission and slippage are charged on every position change (10 + 5 bps per side here). 15.00 bps per side modeled |
| `net_profitability` | fail | **FAILED.** The strategy must still earn after those costs. net total return -44.64% after costs |
| `cost_margin` | skip | How much worse the costs may get before the profit disappears. not profitable after costs |
| `delay_sensitivity` | skip | The result when every fill is one or more bars later; a real edge survives a small delay. not profitable after costs |
| `timing_significance` | skip | Is the timing better than random entries with the same exposure (permutation p-value)? not profitable after costs |
| `sample_size` | pass | Enough closed trades for statistics to mean anything. 41 closed trades (min 30) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.011 over 83 trial(s) |
| `trials_disclosed` | pass | The number of trials was declared and/or counted in the ledger, not left at 1. n_trials declared |
| `holdout_consistency` | pass | The last part of the history must behave like the first part. Sharpe/bar train -0.0049 vs holdout +0.0386 |
| `period_consistency` | skip | The profit must not come from one lucky period. not profitable after costs |
| `walk_forward_stability` | info | Parameters chosen in one window must work in the next. 2 of 6 equal windows (439 bars each) made money; worst -71.3%, best +107.0% |
| `sharpe_confidence` | info | Sharpe 95% interval -0.59 to +0.70 (return -94.9% to +377.5%); 60% of resamples have a positive Sharpe |
| `serial_correlation` | info | serial correlation of returns is small (lag-1 -0.09): Sharpe 0.07, corrected 0.07 |
| `track_record` | info | needs 218,106 bars (about 597.55 years) to be positive at 95%; has 2,633: not enough history yet |
| `benchmark` | info | buy & hold +893.73% (Sharpe 0.81) vs strategy -44.64% (Sharpe 0.07) |
| `alpha_after_beta` | warn | alpha is not significant after beta: beta 0.29 to buy & hold, annual alpha -17.6% (95% interval -46.5% to +11.2%, t=-1.2), 648% of the average return is market exposure |
| `regime_stability` | skip | not profitable after costs |
| `rebalance_timing_luck` | skip | no regular rebalance cadence found (pass rebalance_every to set it) |
| `cost_sensitivity` | skip | not profitable after the modeled costs |
| `cost_realism` | warn | costs look optimistic: the high-low half-spread is 48.7 bps per side against 5.0 bps modeled: total return -44.6% -> -61.3% at the realistic cost |
| `spread_estimate` | info | rough spread estimate from high and low: about 97.39 bps (48.7 bps per side); the model charges only 5 bps slippage per side, well below it: costs may be optimistic |
| `capacity` | info | capital that keeps 90% of 81 fills within a share of the bar's volume: 1%: 526K, 5%: 2.63M, 10%: 5.26M (median bar trades 452M) |
| `trial_ledger` | pass | The hash-chained ledger of variants was intact. 1 variant(s) tried on this data (counted by the ledger) |
| `preregistration` | info | pre-registered at 2026-11-08T16:54:49.269260+00:00: the hypothesis was written before the first verification of this code |

Verdict **REJECT**, ARL **2/9**. ARL 2/9 — blocked at 3: it earns after costs (net_profitability)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.44 | 0.40 | 0.47 | -0.58 | 0.47 | 0.23 | 0.15 | 0.05 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 1.95 | 0.33 | 2.20 |
| 2018 | -1.34 | -0.71 | -0.73 |
| 2019 | -0.27 | -0.18 | 0.94 |
| 2020 | 1.36 | 0.61 | 3.02 |
| 2021 | 1.48 | 0.95 | 0.60 |
| 2022 | -0.70 | -0.42 | -0.64 |
| 2023 | 1.69 | 0.33 | 1.56 |
| 2024 | 0.12 | -0.02 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

Reasons given by the verifier:
- net_profitability: net total return -44.64% after costs
- deflated_sharpe: deflated Sharpe 0.011 over 83 trial(s)
- alpha_after_beta: alpha is not significant after beta: beta 0.29 to buy & hold, annual alpha -17.6% (95% interval -46.5% to +11.2%, t=-1.2), 648% of the average return is market exposure
- cost_realism: costs look optimistic: the high-low half-spread is 48.7 bps per side against 5.0 bps modeled: total return -44.6% -> -61.3% at the realistic cost

## Honest conclusion

Validation gate is CLOSED (REJECT or non-positive Sharpe). The holdout stays sealed; this is a reviewed case.
