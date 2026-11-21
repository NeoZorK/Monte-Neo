# SMA trend filter, ETH: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: trend. Fixed parameters (chosen before any data was read): `{"window": 100}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-12-63c0faa1`; planned Lab-wide trials: 83.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | PASS_WITH_WARNINGS | 4/9 | 1.18 | 0.91 | 4 |
| validation | pre | NEEDS_MORE_EVIDENCE | 3/9 | 0.85 | 0.43 | 83 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`03dc14a1d7fe946b`, pre data)

| Check | Status | What it means |
|---|---|---|
| `data_integrity` | pass | The price table is clean (no NaN, inverted bars or duplicates). A broken table makes every other number meaningless. OHLCV is clean |
| `data_quality` | pass | no spikes, frozen prices, split jumps or gaps |
| `determinism` | pass | The same input must give the same signal; otherwise nothing can be rechecked. signal() is deterministic |
| `lookahead_truncation` | pass | Cutting the future off the data must not change past signals. A change means the signal peeks ahead. truncation probe: no leak detected |
| `lookahead_perturbation` | pass | Changing only future prices must not change today's signal. future-perturbation probe: no leak detected |
| `external_data` | pass | outside data: none read (df only) |
| `repaint_history` | pass | A signal shown at bar t must not be rewritten later. repaint (history): the signal of a closed bar never changed (19 prefixes, +50 bars, revised tail) |
| `repaint_live` | info | repaint (forming bar): decided at the close, flickers while the bar forms (28% of snapshots): act on it only after the bar closes |
| `lookahead_static_lint` | pass | Static scan of the source for shift(-1), centred windows and whole-series statistics. static lint: clean |
| `implausible_accuracy` | pass | next-bar hit rate 0.522 over 1451 bars (z 1.7) |
| `data_independence` | pass | data independence: positions follow the prices |
| `implausible_performance` | pass | Sharpe or accuracy too good to be true is treated as a bug until proven otherwise. annualized Sharpe 0.9 is within the usual range |
| `costs_modeled` | pass | Commission and slippage are charged on every position change (10 + 5 bps per side here). 15.00 bps per side modeled |
| `net_profitability` | pass | The strategy must still earn after those costs. net total return +1040.23% after costs |
| `cost_margin` | pass | How much worse the costs may get before the profit disappears. break-even cost 200.00 bps per side vs 15.00 modeled |
| `delay_sensitivity` | pass | The result when every fill is one or more bars later; a real edge survives a small delay. survives 1 bar execution delay |
| `timing_significance` | warn | Is the timing better than random entries with the same exposure (permutation p-value)? beats 92% of 200 shifted copies of its positions (p 0.090) |
| `sample_size` | pass | Enough closed trades for statistics to mean anything. 48 closed trades (min 30) |
| `deflated_sharpe` | fail | **FAILED.** The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.431 over 83 trial(s) |
| `trials_disclosed` | pass | The number of trials was declared and/or counted in the ledger, not left at 1. n_trials declared |
| `holdout_consistency` | pass | The last part of the history must behave like the first part. Sharpe/bar train +0.0486 vs holdout +0.0335 |
| `period_consistency` | pass | The profit must not come from one lucky period. profitable in 6 of 8 periods |
| `walk_forward_stability` | info | Parameters chosen in one window must work in the next. 4 of 6 equal windows (439 bars each) made money; worst -28.5%, best +813.3% |
| `sharpe_confidence` | info | Sharpe 95% interval +0.08 to +1.62 (return -72.8% to +46229.2%); 99% of resamples have a positive Sharpe |
| `serial_correlation` | info | serial correlation of returns is small (lag-1 -0.02): Sharpe 0.85, corrected 0.72 |
| `track_record` | info | needs 1,423 bars (about 3.9 years) to be positive at 95%; has 2,633 |
| `benchmark` | info | buy & hold +893.73% (Sharpe 0.81) vs strategy +1040.23% (Sharpe 0.85) |
| `alpha_after_beta` | warn | alpha is not significant after beta: beta 0.55 to buy & hold, annual alpha +16.6% (95% interval -18.1% to +51.2%, t=0.9), 71% of the average return is market exposure |
| `regime_stability` | warn | the evidence rests on one regime: 98% of the profit comes from rising markets |
| `rebalance_timing_luck` | skip | no regular rebalance cadence found (pass rebalance_every to set it) |
| `cost_sensitivity` | pass | total return +1040.2% at modeled costs, +887.8% at doubled costs |
| `cost_realism` | warn | costs look optimistic: the high-low half-spread is 48.7 bps per side against 5.0 bps modeled: total return +1040.2% -> +649.2% at the realistic cost |
| `spread_estimate` | info | rough spread estimate from high and low: about 97.39 bps (48.7 bps per side); the model charges only 5 bps slippage per side, well below it: costs may be optimistic |
| `capacity` | info | capital that keeps 90% of 95 fills within a share of the bar's volume: 1%: 981K, 5%: 4.91M, 10%: 9.81M (median bar trades 452M) |
| `trial_ledger` | pass | The hash-chained ledger of variants was intact. 2 variant(s) tried on this data (counted by the ledger) |
| `preregistration` | info | pre-registered at 2026-11-08T16:55:20.006134+00:00: the hypothesis was written before the first verification of this code |

Verdict **NEEDS_MORE_EVIDENCE**, ARL **3/9**. ARL 3/9 — blocked at 4: the signal predicts (timing_significance)

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.67 | 0.63 | 1.46 | -0.75 | 0.61 | 0.37 | 0.50 | 0.13 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 1.96 | 0.56 | 2.20 |
| 2018 | 0.15 | -0.09 | -0.73 |
| 2019 | 1.12 | 0.60 | 0.94 |
| 2020 | 1.32 | 1.05 | 3.02 |
| 2021 | 1.48 | 1.65 | 0.60 |
| 2022 | -1.44 | -0.46 | -0.64 |
| 2023 | 1.15 | 0.49 | 1.56 |
| 2024 | 0.55 | 0.16 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

Reasons given by the verifier:
- deflated_sharpe: deflated Sharpe 0.431 over 83 trial(s)
- timing_significance: beats 92% of 200 shifted copies of its positions (p 0.090)
- alpha_after_beta: alpha is not significant after beta: beta 0.55 to buy & hold, annual alpha +16.6% (95% interval -18.1% to +51.2%, t=0.9), 71% of the average return is market exposure
- regime_stability: the evidence rests on one regime: 98% of the profit comes from rising markets
- cost_realism: costs look optimistic: the high-low half-spread is 48.7 bps per side against 5.0 bps modeled: total return +1040.2% -> +649.2% at the realistic cost

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
