# Trap Suite

The Trap Suite is a set of strategies that are known to lie, each with the verdict the verifier
must return. It lives in [`tests/traps/`](https://github.com/NeoZorK/Monte-Neo/tree/main/tests/traps) and runs on every CI build.
If a change to the verifier stops catching a trap, or starts accusing an honest strategy,
CI fails.

Every trap is a normal strategy file with `signal(df)`. The manifest in
`tests/traps/test_trap_suite.py` gives each file a dataset, the allowed verdicts and the check
statuses that must appear.

## Catalogue

25 traps, 9 honest controls, 2 parameterized strategies for `verify_grid` and a data-snooping test.
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

### Centered windows and filters

| File | How it lies | Caught by |
|------|-------------|-----------|
| `centered_window` | `rolling(..., center=True)` | truncation, perturbation, lint, implausible accuracy |
| `convolve_same` | `np.convolve(mode="same")` centres the kernel | truncation, perturbation, lint, implausible accuracy |
| `fft_denoise` | FFT low-pass over the whole series | truncation, perturbation, lint (warn) |

### Filling gaps from the future

| File | How it lies | Caught by |
|------|-------------|-----------|
| `bfill_leak` | Sparse series backward-filled | truncation, perturbation, lint, implausible accuracy |
| `interpolate_leak` | `interpolate()` uses the next known value | truncation, perturbation, lint |
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

### Aggregates over the current bucket

| File | How it lies | Caught by |
|------|-------------|-----------|
| `hourly_close_leak` | Each minute sees its hour's final close | truncation, perturbation, lint (warn) |
| `resample_max_leak` | Each bar sees the maximum of its 15-minute bucket | truncation, lint (warn) |

### Economics

| File | How it lies | Caught by |
|------|-------------|-----------|
| `high_turnover` | Honest code, but the edge cannot pay its costs | net profitability |
| data snooping (test) | Best of 200 random strategies with `n_trials` hidden | deflated Sharpe once `n_trials` is declared |

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

Grid strategies: `sma_params`, `momentum_params`.

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
