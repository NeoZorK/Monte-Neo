# Turn-of-month seasonality, BTC: automatic review

Idea: Claude Sonnet 5.5. Process, design and verification: Rostyslav Shcherbyna. Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: seasonality. Fixed parameters (chosen before any data was read): `{"first": 28, "last": 3}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-14-edba6c03`; planned Lab-wide trials: 83.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 3/9 | 1.04 | 0.93 | 9 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | 0.54 | 0.15 | 83 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`8a3634f426047572`, pre data)

| Check | Status | What it means |
|---|---|---|
| `data_integrity` | pass | The price table is clean (no NaN, inverted bars or duplicates). A broken table makes every other number meaningless. OHLCV is clean |
| `data_quality` | pass | no spikes, frozen prices, split jumps or gaps |
| `determinism` | pass | The same input must give the same signal; otherwise nothing can be rechecked. signal() is deterministic |
| `lookahead_truncation` | pass | Cutting the future off the data must not change past signals. A change means the signal peeks ahead. truncation probe: no leak detected |
| `lookahead_perturbation` | pass | Changing only future prices must not change today's signal. future-perturbation probe: no leak detected |
| `external_data` | pass | outside data: none read (df only) |
| `repaint_history` | pass | A signal shown at bar t must not be rewritten later. repaint (history): the signal of a closed bar never changed (19 prefixes, +50 bars, revised tail) |
| `repaint_live` | pass | repaint (forming bar): the signal is known at the bar's open and cannot change while it forms |
| `lookahead_static_lint` | pass | Static scan of the source for shift(-1), centred windows and whole-series statistics. static lint: clean |
| `implausible_accuracy` | pass | next-bar hit rate 0.519 over 570 bars (z 0.9) |
| `data_independence` | pass | data independence: positions depend on the calendar only |
| `implausible_performance` | pass | Sharpe or accuracy too good to be true is treated as a bug until proven otherwise. annualized Sharpe 0.5 is within the usual range |
| `costs_modeled` | pass | Commission and slippage are charged on every position change (10 + 5 bps per side here). 15.00 bps per side modeled |
| `net_profitability` | pass | The strategy must still earn after those costs. net total return +127.36% after costs |
| `cost_margin` | pass | How much worse the costs may get before the profit disappears. break-even cost 62.05 bps per side vs 15.00 modeled |
| `delay_sensitivity` | pass | The result when every fill is one or more bars later; a real edge survives a small delay. survives 1 bar execution delay |
| `timing_significance` | warn | Is the timing better than random entries with the same exposure (permutation p-value)? beats 76% of 200 shifted copies of its positions (p 0.244) |
| `sample_size` | pass | Enough closed trades for statistics to mean anything. 87 closed trades (min 30) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.153 over 83 trial(s) |
| `trials_disclosed` | pass | The number of trials was declared and/or counted in the ledger, not left at 1. n_trials declared |
| `holdout_consistency` | pass | The last part of the history must behave like the first part. Sharpe/bar train +0.0351 vs holdout +0.0053 |
| `period_consistency` | pass | The profit must not come from one lucky period. profitable in 6 of 8 periods |
| `walk_forward_stability` | info | Parameters chosen in one window must work in the next. 3 of 6 equal windows (439 bars each) made money; worst -7.4%, best +82.9% |
| `sharpe_confidence` | info | Sharpe 95% interval -0.26 to +1.26 (return -57.7% to +910.8%); 91% of resamples have a positive Sharpe |
| `serial_correlation` | info | serial correlation of returns is small (lag-1 -0.03): Sharpe 0.54, corrected 0.52 |
| `track_record` | info | needs 3,325 bars (about 9.11 years) to be positive at 95%; has 2,633: not enough history yet |
| `benchmark` | info | buy & hold +1521.24% (Sharpe 0.91) vs strategy +127.36% (Sharpe 0.54) |
| `alpha_after_beta` | warn | alpha is not significant after beta: beta 0.16 to buy & hold, annual alpha +5.0% (95% interval -14.4% to +24.4%, t=0.5), 68% of the average return is market exposure |
| `regime_stability` | warn | the evidence rests on one regime: 98% of the profit comes from volatile markets |
| `rebalance_timing_luck` | warn | the result is the luck of the rebalance day: 12 rebalance phases of 24 bars: worst -58.2%, mean +42.3%, best +232.4% |
| `cost_sensitivity` | pass | total return +127.4% at modeled costs, +75.1% at doubled costs |
| `cost_realism` | warn | costs look optimistic: the high-low half-spread is 37.9 bps per side against 5.0 bps modeled: total return +127.4% -> +28.2% at the realistic cost |
| `spread_estimate` | info | rough spread estimate from high and low: about 75.78 bps (37.89 bps per side); the model charges only 5 bps slippage per side, well below it: costs may be optimistic |
| `capacity` | info | capital that keeps 90% of 173 fills within a share of the bar's volume: 1%: 1.92M, 5%: 9.6M, 10%: 19.2M (median bar trades 997M) |
| `trial_ledger` | pass | The hash-chained ledger of variants was intact. 4 variant(s) tried on this data (counted by the ledger) |
| `preregistration` | info | pre-registered at 2026-11-08T16:55:25.095300+00:00: the hypothesis was written before the first verification of this code |

Verdict **NEEDS_MORE_EVIDENCE**, ARL **3/9**. ARL 3/9 — blocked at 4: the signal predicts (timing_significance)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.43 | 0.28 | 0.35 | -0.32 | 0.39 | 0.15 | 0.27 | 0.05 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 2.02 | 0.35 | 2.20 |
| 2018 | -1.00 | -0.33 | -0.73 |
| 2019 | 0.85 | 0.24 | 0.94 |
| 2020 | 1.24 | 0.40 | 3.02 |
| 2021 | 1.19 | 0.39 | 0.60 |
| 2022 | 0.39 | 0.07 | -0.64 |
| 2023 | 0.71 | 0.11 | 1.56 |
| 2024 | -0.72 | -0.18 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

Reasons given by the verifier:
- deflated_sharpe: deflated Sharpe 0.153 over 83 trial(s)
- timing_significance: beats 76% of 200 shifted copies of its positions (p 0.244)
- alpha_after_beta: alpha is not significant after beta: beta 0.16 to buy & hold, annual alpha +5.0% (95% interval -14.4% to +24.4%, t=0.5), 68% of the average return is market exposure
- regime_stability: the evidence rests on one regime: 98% of the profit comes from volatile markets
- rebalance_timing_luck: the result is the luck of the rebalance day: 12 rebalance phases of 24 bars: worst -58.2%, mean +42.3%, best +232.4%
- cost_realism: costs look optimistic: the high-low half-spread is 37.9 bps per side against 5.0 bps modeled: total return +127.4% -> +28.2% at the realistic cost

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
