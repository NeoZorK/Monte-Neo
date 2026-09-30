# Trap of the week

A weekly post series: one way a backtest lies, the smallest code that shows it, and how the verifier catches
it. Every post runs on `synthetic_ohlcv(3000, seed=1)`, a random walk with no edge, so any profit is an
artefact. The strategies are in
[`tests/traps/strategies/`](https://github.com/NeoZorK/Monte-Neo/tree/main/tests/traps/strategies).
The numbers were produced with v0.41.0. Post at most one a week and follow the
[rules for all posts](launch-kit.md#rules-for-all-posts).

Post shape (about 150 words): the tempting idea, the code, what the verifier says, the fix, the link.

| # | Trap | File | Verdict on the random walk | What catches it |
|---|------|------|----------------------------|-----------------|
| 1 | Random split of a time series | `shuffled_split_fit` | REJECT | truncation probe |
| 2 | K-fold without a gap | `kfold_no_gap` | REJECT | truncation and perturbation probes |
| 3 | Best start date picked with hindsight | `best_start_date` | REJECT | truncation and perturbation probes |
| 4 | Position size from the whole series' volatility | `vol_target_full` | REJECT | probes and the static lint (`full_sample_stat`) |
| 5 | The day's close on every bar of the day | `daily_close_transform` | REJECT | probes and the lint (`group_aggregate`) |
| 6 | A daily table joined without a one-day shift | `merge_asof_daily_no_shift` | REJECT | probes and the lint |
| 7 | Resample with `closed="right"` | `resample_left_closed_right` | REJECT | probes and the lint |
| 8 | Min-max scaling on the whole series | `minmax_full_scale` | REJECT | probes and the lint |
| 9 | PCA fitted on the whole sample | `pca_full_sample` | REJECT | truncation probe and the lint |
| 10 | Winsorizing at whole-sample percentiles | `winsorize_full` | REJECT | probes and the lint |
| 11 | Feature chosen by its correlation with the future | `feature_select_future_corr` | REJECT | probes |
| 12 | Hyper-parameters tuned on the test sample | `hyperparam_fit_full` | REJECT | probes |

## Drafts

### 1. Shuffling a time series

> Split your data at random into 70% train and 30% test, fit, and the test looks great. On prices it is a leak:
> a shuffled split puts the bars around each test bar into the training set.
>
> ```python
> idx = np.random.default_rng(0).permutation(len(x))[: int(0.7 * len(x))]
> coef = np.linalg.lstsq(x[idx], y[idx], rcond=None)[0]
> return np.sign(lags @ coef)
> ```
>
> The static lint stays quiet here (no sklearn call). The truncation probe does not: cut the data at bar *t* and
> the signal at bar *t* changes. `REJECT`. Fit only on bars before the ones you predict, with a gap.

### 2. K-fold cross-fitting

> `KFold` is fine for independent rows. Returns are not independent: neighbouring folds share the same market
> regime. Each fold predicted by a model trained on all the others uses the future.
>
> Verdict: `REJECT`, truncation and perturbation probes fail. With scikit-learn the lint also flags
> `KFold(shuffle=True)` and `train_test_split(shuffle=True)` (rules `kfold_split`, `shuffled_split`). Use
> `TimeSeriesSplit(gap=...)`.

### 3. The best start date

> "Start trading on the date that gave the best result" is a fit on the whole sample, even with one parameter.
>
> ```python
> start = max(candidates, key=lambda s: close[-1] / close[s])
> ```
>
> The position at every bar depends on the last close of the dataset. Truncation and perturbation probes fail.

### 4. Volatility targeting with the whole series' volatility

> `size = 1 / (1 + 1000 * returns.std())` looks like risk management. The `std()` includes every future bar.
>
> Verdict `REJECT`; the lint names the rule (`full_sample_stat`) and the line. The honest twin uses an expanding
> window (`vol_target_expanding`) and is not flagged.

### 5-7. Calendar joins

> Three ways to put a slower series on a faster one: `groupby(date).transform("last")`, `merge_asof` on the day's
> label, `resample(closed="right")`. In each, the value stamped early in a period is a value computed at its end.
>
> Fix: shift the daily value by one period before broadcasting (`daily_close_shifted`,
> `merge_asof_daily_shifted`, `resample_closed_left_shifted` are the honest controls that stay unflagged).

### 8-10. Whole-sample transforms

> Min-max scaling, PCA and winsorizing are one-line preprocessing steps that fit their parameters on all of
> the data. Each leaks the future extremes into the past. The probes catch them; the lint warns on the
> call. The honest version fits on the past only (`expanding_winsorize`).

### 11-12. Choosing with hindsight

> Picking the most predictive lag, or the best moving-average length, "on the training data" is honest only
> if the training data ends before the test data begins. On one sample it is selection bias with a leak on top.
> The verifier flags the leak; for the selection itself, declare `n_trials` or use `verify_grid` so the Deflated
> Sharpe prices it.

## After the series

Collect the twelve posts into one article and link it from the README. Every post that draws a new question is
a candidate for a [trap submission](https://github.com/NeoZorK/Monte-Neo/issues/new?template=trap_submission.yml).
