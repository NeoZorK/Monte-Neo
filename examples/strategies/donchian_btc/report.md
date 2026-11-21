# Donchian breakout 55/20, BTC: automatic review

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not predict future returns.

Family: breakout. Fixed parameters (chosen before any data was read): `{"entry": 55, "exit": 20}`. Costs: 10 bps commission + 5 bps slippage per side, fills on the next bar.

Data: discovery before 2021-01-01, validation 2021-01-01 to 2025-01-01, sealed holdout from 2025-01-01.

Hypothesis registered before testing: `reg-2-0c0bcf97`; planned Lab-wide trials: 83.

## Pipeline

| Stage | Data | Verdict | ARL | Sharpe | Deflated Sharpe | Trials |
|---|---|---|---|---|---|---|
| discovery | disc | NEEDS_MORE_EVIDENCE | 4/9 | 1.92 | 1.00 | 6 |
| validation | pre | NEEDS_MORE_EVIDENCE | 4/9 | 1.30 | 0.86 | 83 |
| holdout | not run | | | | | |

## Checks of the validation certificate (`bf5c4588371d70de`, pre data)

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
| `implausible_accuracy` | pass | next-bar hit rate 0.534 over 984 bars (z 2.1) |
| `data_independence` | pass | data independence: positions follow the prices |
| `implausible_performance` | pass | Sharpe or accuracy too good to be true is treated as a bug until proven otherwise. annualized Sharpe 1.3 is within the usual range |
| `costs_modeled` | pass | Commission and slippage are charged on every position change (10 + 5 bps per side here). 15.00 bps per side modeled |
| `net_profitability` | pass | The strategy must still earn after those costs. net total return +2701.08% after costs |
| `cost_margin` | pass | How much worse the costs may get before the profit disappears. break-even cost 200.00 bps per side vs 15.00 modeled |
| `delay_sensitivity` | pass | The result when every fill is one or more bars later; a real edge survives a small delay. survives 1 bar execution delay |
| `timing_significance` | pass | Is the timing better than random entries with the same exposure (permutation p-value)? beats 100% of 200 shifted copies of its positions (p 0.010) |
| `sample_size` | fail | **FAILED.** Enough closed trades for statistics to mean anything. 22 closed trades (min 30) |
| `deflated_sharpe` | warn | The Sharpe ratio after paying for every variant tried (n_trials counts ALL ideas and grids of the Lab, not only this one). deflated Sharpe 0.856 over 83 trial(s) |
| `trials_disclosed` | pass | The number of trials was declared and/or counted in the ledger, not left at 1. n_trials declared |
| `holdout_consistency` | pass | The last part of the history must behave like the first part. Sharpe/bar train +0.0620 vs holdout +0.0888 |
| `period_consistency` | pass | The profit must not come from one lucky period. profitable in 6 of 8 periods |
| `walk_forward_stability` | info | Parameters chosen in one window must work in the next. 5 of 6 equal windows (439 bars each) made money; worst -6.1%, best +198.1% |
| `sharpe_confidence` | info | Sharpe 95% interval +0.48 to +2.03 (return +126.5% to +36786.1%); 100% of resamples have a positive Sharpe |
| `serial_correlation` | info | returns are serially correlated (lag-1 +0.04): the annualized Sharpe 1.30 is about 0.98 after the correction (Lo), 25% lower |
| `track_record` | info | needs 552 bars (about 1.51 years) to be positive at 95%; has 2,633 |
| `benchmark` | info | buy & hold +1521.24% (Sharpe 0.91) vs strategy +2701.08% (Sharpe 1.30) |
| `alpha_after_beta` | pass | beta 0.36 to buy & hold, annual alpha +32.2% (95% interval +6.7% to +57.6%, t=2.5), 42% of the average return is market exposure |
| `regime_stability` | warn | the evidence rests on one regime: loses in falling markets (-8.9% over 38% of bars); 104% of the profit comes from rising markets; loses in volatile markets (-36.4% over 50% of bars); 119% of the profit comes from calm markets |
| `rebalance_timing_luck` | skip | no regular rebalance cadence found (pass rebalance_every to set it) |
| `cost_sensitivity` | pass | total return +2701.1% at modeled costs, +2528.2% at doubled costs |
| `cost_realism` | warn | costs look optimistic: the high-low half-spread is 37.9 bps per side against 5.0 bps modeled: total return +2701.1% -> +2323.4% at the realistic cost |
| `spread_estimate` | info | rough spread estimate from high and low: about 75.78 bps (37.89 bps per side); the model charges only 5 bps slippage per side, well below it: costs may be optimistic |
| `capacity` | info | capital that keeps 90% of 43 fills within a share of the bar's volume: 1%: 2.88M, 5%: 14.4M, 10%: 28.8M (median bar trades 997M) |
| `trial_ledger` | pass | The hash-chained ledger of variants was intact. 1 variant(s) tried on this data (counted by the ledger) |
| `preregistration` | info | pre-registered at 2026-11-08T16:54:49.279928+00:00: the hypothesis was written before the first verification of this code |

Verdict **NEEDS_MORE_EVIDENCE**, ARL **4/9**. ARL 4/9 — not assessed beyond 4: it is new alpha (hidden_short_volatility (not run), residual_alpha (not run))

## Independent economics (validation period, net of costs, before the holdout)

| Net Sharpe | Net Sharpe, costs x2 | Total return | Max drawdown | Corr. with BTC | Beta share (corr^2) | Alpha t vs BTC | Deflated Sharpe | BTC buy&hold Sharpe |
|---|---|---|---|---|---|---|---|---|
| 0.97 | 0.94 | 2.19 | -0.39 | 0.59 | 0.35 | 1.25 | 0.30 | 0.78 |

By calendar year, all years before the holdout (regimes):

| Year | Net Sharpe | Return | BTC return |
|---|---|---|---|
| 2017 | 2.93 | 1.28 | 2.20 |
| 2018 | -1.59 | -0.23 | -0.73 |
| 2019 | 1.79 | 1.13 | 0.94 |
| 2020 | 2.33 | 1.50 | 3.02 |
| 2021 | 0.91 | 0.40 | 0.60 |
| 2022 | -2.08 | -0.27 | -0.64 |
| 2023 | 1.88 | 0.76 | 1.56 |
| 2024 | 1.67 | 0.78 | 1.21 |

Notes: daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe.

Reasons given by the verifier:
- sample_size: 22 closed trades (min 30)
- deflated_sharpe: deflated Sharpe 0.856 over 83 trial(s)
- regime_stability: the evidence rests on one regime: loses in falling markets (-8.9% over 38% of bars); 104% of the profit comes from rising markets; loses in volatile markets (-36.4% over 50% of bars); 119% of the profit comes from calm markets
- cost_realism: costs look optimistic: the high-low half-spread is 37.9 bps per side against 5.0 bps modeled: total return +2701.1% -> +2323.4% at the realistic cost

## Honest conclusion

Validation gate is open: the candidate may be frozen and the holdout opened once.
