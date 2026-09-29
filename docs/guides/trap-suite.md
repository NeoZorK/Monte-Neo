# Trap Suite

The Trap Suite is a set of strategies that are known to lie, each with the verdict the verifier
must return. It lives in [`tests/traps/`](https://github.com/NeoZorK/Monte-Neo/tree/main/tests/traps) and runs on every CI build.
If a change to the verifier stops catching a trap, or starts accusing an honest strategy,
CI fails.

Every trap is a normal strategy file with `signal(df)`. The manifest in
`tests/traps/test_trap_suite.py` gives each file a dataset, the allowed verdicts and the check
statuses that must appear.

## Catalogue

80 traps, 35 honest controls, 2 parameterized strategies for `verify_grid` and a data-snooping test.
"Caught by" lists the checks that flag each trap on the random-walk dataset. "lint (warn)" is a
warning only; the dynamic probes produce the `REJECT`.

### Shifted or reversed time

| File | How it lies | Caught by |
|------|-------------|-----------|
| `lookahead_shift` | `shift(-1)` puts the next close into today's signal | truncation, perturbation, lint, implausible accuracy |
| `diff_negative` | `diff(-1)` is the next bar's return | truncation, perturbation, lint, implausible accuracy |
| `pct_change_negative` | `pct_change(periods=-3)` compares with three bars ahead | truncation, perturbation, lint, implausible accuracy |
| `roll_negative` | `np.roll(x, -1)` pulls tomorrow into today | truncation, perturbation, lint, implausible accuracy |
| `reverse_rolling` | Rolling window over a reversed series | truncation, perturbation, lint, implausible accuracy |
| `last_row_leak` | Every bar compared with `.iloc[-1]`, the final close | truncation, perturbation, lint |
| `gradient_leak` | `np.gradient` uses central differences (bar t + 1) | truncation, perturbation, lint, implausible accuracy |
| `reversed_cummax` | `cummax` over the reversed series is the highest price still to come | truncation, perturbation, lint |
| `reversed_accumulate` | `np.maximum.accumulate` over the reversed array | truncation, perturbation, lint |
| `forward_window_indexer` | `FixedForwardWindowIndexer` makes `rolling()` look ahead | truncation, perturbation, lint, implausible accuracy |
| `tail_threshold` | Threshold from `.tail(500).mean()`, the last bars of the dataset | truncation, perturbation, lint |
| `iat_last` | `.iat[-1]` reads the final close | truncation, perturbation, lint |
| `flip_cumsum` | `np.flip(np.cumsum(np.flip(ret)))` sums the returns still to come | truncation, perturbation, lint |
| `shift_variable` | `horizon = -1; close.shift(horizon)`: the negative shift hides in a variable | truncation, perturbation, lint, implausible accuracy |

### Centered windows and filters

| File | How it lies | Caught by |
|------|-------------|-----------|
| `centered_window` | `rolling(..., center=True)` | truncation, perturbation, lint, implausible accuracy |
| `convolve_same` | `np.convolve(mode="same")` centres the kernel | truncation, perturbation, lint, implausible accuracy |
| `centered_variable` | `centred = True; rolling(21, center=centred)` | truncation, perturbation, lint, implausible accuracy |
| `fft_denoise` | FFT low-pass over the whole series | truncation, perturbation, lint (warn) |

### Filling gaps from the future

| File | How it lies | Caught by |
|------|-------------|-----------|
| `bfill_leak` | Sparse series backward-filled | truncation, perturbation, lint, implausible accuracy |
| `interpolate_leak` | `interpolate()` uses the next known value | truncation, perturbation, lint |
| `reindex_nearest` | `reindex(method="nearest")` aligns bars with the next hour's close | truncation, perturbation, lint |
| `np_interp_fill` | `np.interp` draws a line to the next known point across gaps | truncation, perturbation, lint |
| `merge_asof_forward` | `merge_asof(direction="forward")` | truncation, perturbation, lint |

### Whole-sample statistics

| File | How it lies | Caught by |
|------|-------------|-----------|
| `global_zscore` | z-score with the mean and std of the whole series | truncation, perturbation, lint (warn) |
| `numpy_global_stat` | `np.mean` / `np.std` thresholds over the whole array | truncation, perturbation, lint (warn) |
| `full_rank` | Percentile rank against the whole history | truncation, perturbation, lint (warn) |
| `qcut_full` | `pd.qcut` quantile buckets of the whole sample | perturbation, lint (warn) |
| `argsort_rank` | Double `argsort` rank against the whole sample | truncation, perturbation, lint (warn) |
| `idxmax_leak` | Long until the bar of the all-time high | perturbation, lint (warn) |
| `cumsum_total_norm` | Cumulative share of the whole-sample total | truncation, lint (warn) |
| `full_polyfit` | Trend fitted once on the whole series | truncation, perturbation, lint (warn) |
| `target_encoding_leak` | Mean forward return per bucket, fitted on everything | truncation, perturbation, lint |
| `sort_values_rank` | `sort_values` ranks every bar among all prices | truncation, perturbation, lint (warn) |
| `np_sort_rank` | `np.sort` + `searchsorted` ranks each close among all closes | truncation, perturbation, lint (warn) |
| `cut_auto_bins` | `pd.cut(bins=5)` takes edges from the whole-series min and max | truncation, perturbation, lint (warn) |
| `builtin_max` | Python's `max()` over the whole column | perturbation, lint (warn) |
| `describe_threshold` | Quartiles from `describe()` over the whole series | truncation, perturbation, lint (warn) |
| `agg_zscore` | z-score from `agg(["mean", "std"])` over the whole series | truncation, perturbation, lint (warn) |
| `mode_level` | `round(-1).mode()`: most frequent level over the whole dataset | truncation, perturbation, lint (warn) |
| `value_counts_level` | `value_counts().idxmax()`: busiest level, future included | truncation, perturbation, lint (warn) |
| `nlargest_dates` | `nlargest(100)` finds the dataset's highest closes | perturbation, lint (warn) |

### Aggregates over the current bucket

| File | How it lies | Caught by |
|------|-------------|-----------|
| `hourly_close_leak` | Each minute sees its hour's final close | truncation, perturbation, lint (warn) |
| `resample_max_leak` | Each bar sees the maximum of its 15-minute bucket | truncation, lint (warn) |
| `hourly_close_map` | `groupby().last()` mapped back onto every minute of the hour | truncation, perturbation, lint (warn) |
| `hour_size_leak` | `transform("size")` knows how many bars the hour will have | truncation, lint (warn) |
| `bars_left_in_hour` | `cumcount(ascending=False)` counts the bars still to come | truncation, lint |
| `resample_ffill_max` | `resample("h").max()` forward-filled from the hour's first minute | truncation, lint (warn) |

### Machine-learning leaks and pipelines

Fitting a model, a scaler or a threshold on the whole sample, splitting a time series at random,
choosing a start date by its result: the leak is in the workflow, not in one call. The lint knows
`train_test_split(shuffle=True)` and the shuffling splitters (`KFold(shuffle=True)`,
`ShuffleSplit`, ...); the rest is caught by the probes.

| File | How it lies | Caught by |
|------|-------------|-----------|
| `append_nan_shift` | The next close from slicing and appending NaN: a `shift(-1)` without `shift()` | truncation, perturbation, implausible accuracy |
| `best_start_date` | The start date is picked by the buy-and-hold return from it to the end of the sample | truncation, perturbation |
| `feature_select_future_corr` | Picks the lag most correlated with the next return over the whole sample | truncation, perturbation |
| `hyperparam_fit_full` | The moving-average length is tuned on the whole sample, then tested on it | truncation, perturbation |
| `kfold_no_gap` | 5-fold cross-fitting on a time series: the training folds contain the future | truncation, perturbation |
| `shuffled_split_fit` | Least squares fitted on a random 70% of all bars, used on every bar | truncation |
| `knn_random_neighbors` | Nearest-neighbour vote over all bars, later ones included | truncation, perturbation, lint (warn) |
| `pca_full_sample` | First principal component of lagged returns from the whole sample | truncation, lint (warn) |
| `minmax_full_scale` | Min-max scaling with the whole series' minimum and maximum | truncation, perturbation, lint (warn) |
| `winsorize_full` | Returns clipped at the whole sample's 1st and 99th percentiles | truncation, perturbation, lint (warn) |
| `vol_target_full` | Position size from the volatility of the whole series | truncation, perturbation, lint (warn) |
| `size_by_full_drawdown` | Leverage chosen from the maximum drawdown of the whole series | truncation, perturbation, lint (warn) |
| `loop_next_compare` | A loop that compares each bar with the next one | truncation, perturbation, lint (warn), implausible accuracy |

### Calendar joins and resampling

| File | How it lies | Caught by |
|------|-------------|-----------|
| `daily_close_transform` | Each day's final close broadcast to every bar of the day (`transform("last")`) | truncation, perturbation, lint (warn) |
| `day_vwap_total` | The day's total VWAP, later bars included, against the current price | truncation, perturbation, lint (warn) |
| `merge_asof_daily_no_shift` | A daily close merged onto intraday bars with `merge_asof`, not shifted by a day | truncation, perturbation, lint (warn) |
| `resample_left_closed_right` | `resample(label="left", closed="right")`: the value at a bin's start is its last close | truncation, perturbation, lint (warn) |

### Invisible to the static lint

These leak without any suspicious call. Only the dynamic probes catch them, which is why Monte-Neo
runs the strategy instead of only reading it.

| File | How it lies | Caught by |
|------|-------------|-----------|
| `dataset_fraction` | `np.arange(len(df)) / len(df)`: a bar's position depends on how many bars come later | truncation |
| `block_mean_reshape` | `reshape(-1, 60).mean(axis=1).repeat(60)`: every bar sees the rest of its block | truncation, perturbation |

### Invisible to the dynamic probes

The probes rewrite `df` and compare signals. A strategy that ignores `df` and loads the dataset
itself sees the untouched future, so the probes pass. The outside-data watch records every data
file read and network connection made while strategy code runs.

| File | How it lies | Caught by |
|------|-------------|-----------|
| `reads_dataset_file` | Loads the full CSV at import and reads 20 bars ahead of each `df` row | outside data, lint |
| `kmeans_regime_full` | Volatility regimes from 2-means clustering fitted on the whole sample | lint (warn) only: the probes do not move it |

### Universes (several symbols)

A table with a `symbol` column is a universe: `signal(df)` returns a weight per row. The probes
cut and rewrite the future of every symbol at once, so a leak through another symbol is caught
too. A universe in which no symbol stops trading is flagged for survivorship bias.

| File | How it lies | Caught by |
|------|-------------|-----------|
| `xs_next_return_rank` | Ranks symbols by the next bar's return (`groupby("symbol").shift(-1)`) | truncation, perturbation, lint, implausible accuracy |
| `xs_market_future_join` | Joins tomorrow's average return of all symbols onto today's rows | truncation, perturbation |
| `xs_symbol_history_rank` | Ranks each symbol's price against its whole history | perturbation, lint (warn) |
| `xs_future_vol_rank` | Ranks symbols by their future five-bar volatility | truncation, perturbation, lint |
| `xs_pick_winners` | Holds only symbols whose total return over the whole sample is positive | truncation, perturbation, lint |
| `xs_todays_members` | Today's membership applied to the past: only symbols still trading on the last date | truncation, lint (warn) |
| `xs_weights_total_norm` | Momentum signs normalised by the sum over all rows of the sample, not the current cross-section | truncation |
| survivors only (test) | Every symbol trades until the last bar | survivorship (warn) |

### Economics

| File | How it lies | Caught by |
|------|-------------|-----------|
| `high_turnover` | Honest code, but the edge cannot pay its costs | net profitability |
| data snooping (test) | Best of 200 random strategies with `n_trials` hidden | deflated Sharpe once `n_trials` is declared |

### Bad reports

Honest code on honest data can still come with an inflated report. `--claim` compares the reported numbers with the
verified ones.

| Trap | How it lies | Caught by |
|------|-------------|-----------|
| overclaim (test) | Momentum with a real edge, reported with a Sharpe and a return far above what the backtest reproduces | claim consistency |

### Bad data

Honest code can still earn fake money when the prices are wrong. The `bad_ticks` dataset is an
hourly random walk with 40 one-bar bad ticks: a close off by 15% that the next bar undoes.
The `frozen_feed`, `unadjusted_split` and `feed_outages` datasets carry stale stretches, an
unadjusted 2-for-1 split and outages; the code is honest, so the verifier must warn about the data.

| File | How it lies | Caught by |
|------|-------------|-----------|
| `spike_fade` | Fades one-bar moves over 5%: almost all of its profit is the bad ticks | data quality |
| `dip_buyer` | Buys after a 20% drop in three bars: on an unadjusted split that is a fake crash | data quality (warn) |
| `fade_last_move` | Fades the last bar's move on a feed with frozen stretches | data quality (warn) |
| `trend_bars` | Follows the last three bars on a feed with outages | data quality (warn) |

### Honest controls

Honest controls must never fail a look-ahead check. False alarms cost as much trust as missed
leaks.

| File | Pattern |
|------|---------|
| `sma_cross` | SMA crossover |
| `ewm_cross` | EMA crossover |
| `momentum` | One-bar momentum on a dataset with a real edge (must `PASS`) |
| `expanding_zscore` | z-score against expanding mean and std |
| `expanding_rank` | Percentile rank within the past only |
| `resample_shifted` | Previous completed bucket, carried forward |
| `cummax_drawdown` | Drawdown from the running peak |
| `convolve_causal` | Trailing average via `np.convolve(mode="full")[:n]` |
| `rolling_quantile_band` | Breakout above a lagged rolling quantile |
| `prev_hour_close_map` | Previous completed hour: `groupby().last().shift(1)` |
| `bars_into_hour` | `cumcount()` counts only bars already seen |
| `expanding_quantile_band` | Expanding quantile of past closes, shifted by one bar |
| `cut_fixed_bins` | `pd.cut` with explicit, fixed bin edges |
| `hour_running_high` | Running high of the hour so far: `groupby().cummax()` |
| `rolling_min_periods` | `rolling(50, min_periods=1)` |
| `rolling_apply_span` | `rolling().apply(lambda w: w[-1] - w[0])`: `w[-1]` is the current bar |
| `hour_open_ref` | `transform("first")`: the hour's first close is already known |
| `loop_window_breakout` | Breakout in a loop over trailing slices `c[i - 20:i]` with an ATR stop |
| `loop_slice_crossover` | SMA crossover computed in a loop from `c[i - 10:i + 1]` |
| `rolling_polyfit_slope` | `np.polyfit` inside `rolling(30).apply`: each fit sees one window |
| `rsi_loop` | Wilder RSI updated bar by bar |
| `expanding_quantile_breakout` | A real edge on momentum data: hit rate ~0.6 must not be called look-ahead |
| `xs_momentum_rank` | Universe: past 20-bar return ranked within each timestamp (`groupby(df["timestamp"]).rank()`) |
| `xs_equal_weight` | Universe: `+1` on every symbol; the gross cap turns it into equal weights |
| `expanding_max_breakout` | `expanding().max().shift(1)` |
| `daily_close_shifted` | Previous day's close (`groupby(date).last().shift(1)`) broadcast to the day |
| `day_vwap_running` | The day's running VWAP from cumulative sums within the day |
| `expanding_fit_gap` | Model refitted every 300 bars on all earlier bars, with a gap |
| `walk_forward_lstsq_gap` | Least squares refitted every 250 bars on the previous 500, with a 5-bar gap |
| `expanding_winsorize` | Returns clipped at expanding (past-only) percentiles |
| `vol_target_expanding` | Position size from the expanding volatility |
| `merge_asof_daily_shifted` | A daily close shifted by one day, merged with `merge_asof` |
| `resample_closed_left_shifted` | 30-minute bars with `closed="left"`, shifted by one bar |
| `xs_cross_section_norm` | Universe: signs normalised by the current timestamp's cross-section only |
| `xs_point_in_time_members` | Universe: a symbol is held once it has 20 bars of history (point-in-time membership) |

Grid strategies: `sma_params`, `momentum_params`.

### Known limits

- A symbol that is delisted at a zero return (the price simply stops, no crash) looks like a
  normal end of history; the suite has no trap for it yet.
- `kmeans_regime_full` is flagged by the lint only: the probes leave a global clustering nearly
  unchanged, so without the lint it would pass.

## Contribute a trap

Found a way an agent fooled itself? Send it as a trap.

1. Open a [trap submission](https://github.com/NeoZorK/Monte-Neo/issues/new?template=trap_submission.yml)
   issue, or send a PR directly.
2. Add `tests/traps/strategies/<name>.py`:
   - The first line is a docstring that starts with `TRAP:` or `HONEST:` and says how it lies.
   - Define `signal(df)` using only pandas and numpy.
   - Keep it minimal: the smallest code that reproduces the mistake.
3. Add a row to `TRAPS` in `tests/traps/test_trap_suite.py`:
   `(name, dataset, allowed_verdicts, required_check_statuses)`. Use `random_walk` for leaks
   (no edge exists, so any profit is suspicious) and `planted` for a real edge.
   Add honest controls to `HONEST` too.
4. Add the file to the catalogue above. A test checks that every strategy file is listed here.
5. Run `uv run pytest tests/traps tests/unit/test_verify_grid.py`.

If the verifier does not catch your trap yet, still send it. Mark the row with the verdict it
gets today and describe the miss in the PR. A known miss is a roadmap item.
