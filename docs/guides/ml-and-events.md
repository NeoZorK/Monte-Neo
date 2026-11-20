# Machine-learning strategies and event data

Two leaks that no line of code shows: a model fitted on the whole file, and events joined by the time they happened
instead of the time they became public. Monte-Neo takes both decisions away from the strategy.

## The `fit` / `predict` protocol

A model fitted inside `signal(df)` on every row still reacts to its input row by row, so the look-ahead probes cannot
see that it learned from the future. Define two functions instead of `signal`:

```python
import numpy as np

REFIT_EVERY = 63     # bars between refits
MIN_TRAIN = 252      # bars before the first prediction
LABEL_HORIZON = 1    # bars a training label looks ahead
EMBARGO = 5          # extra bars between the training rows and the first predicted row


def fit(train):
    """Return any object: a fitted estimator, coefficients, a dict."""
    ...


def predict(model, df):
    """One position per row of df (+1 / 0 / -1 or weights)."""
    ...
```

```bash
monte-neo verify --ohlcv data.csv --strategy model.py
```

The verifier runs the walk-forward itself. Each block of `REFIT_EVERY` bars is predicted by a model fitted on rows
`[0, start − LABEL_HORIZON − EMBARGO)`, so no prediction comes from a model that saw its own future. The look-ahead
probes then test `predict`. Fitted models are cached by their exact training rows, so the probes do not refit for nothing.

| Check | What it says |
|-------|--------------|
| `ml_refit_gap` | The Sharpe with honest refitting against the Sharpe of `predict(fit(df), df)`, the usual whole-file backtest. `fail` (look-ahead) when the in-sample edge is real and the walk-forward loses money: the profit lived in the fit. `warn` when less than half the edge survives. |
| `ml_cv_overlap` | If the file defines `cv_splits(df)` (a list of `(train_rows, test_rows)`): training rows whose labels reach into a test fold, or that sit inside the embargo after it. Purge them. |

Two more checks are optional:

- `ml_seed_stability`: set `SEEDS = 5` and give `fit` a `seed` argument. The walk-forward runs once per seed, and a
  result whose sign or size depends on the seed is flagged.
- `ml_feature_drift`: define `features(df)`. The population stability index of each feature between the first
  training window and the predicted period is reported, with a warning above 0.25.

### Cross-validation protocol and leakage detectors

`monte_neo.verify.ml_checks` provides the honest splitters, and the verifier checks the rest. Return the splits from
`cv_splits(df)`:

```python
from monte_neo.verify.ml_checks import purged_kfold_splits, cpcv_splits

def cv_splits(df):
    return purged_kfold_splits(len(df), k=5, label_horizon=LABEL_HORIZON, embargo=EMBARGO)
    # or: cpcv_splits(len(df), n_groups=6, n_test_groups=2, label_horizon=LABEL_HORIZON, embargo=EMBARGO)
```

Purged K-fold keeps the folds in time order, drops every training row whose label reaches the test fold, and adds an
embargo after it. Combinatorial purged cross-validation tests every choice of `n_test_groups` blocks (C(6, 2) = 15 splits
rebuild C(5, 1) = 5 full backtest paths), so the result is a distribution of paths, not one lucky split.

More optional hooks, each switching on one certificate row. Every row has a `next_actions` entry when it warns or fails.

| Hook or constant | Row | What it says |
|------------------|-----|--------------|
| `cv_splits(df)` | `ml_cv_shuffle` | `warn` when the test folds are scattered over time (mean run shorter than 5 rows): a shuffled K-fold trains on the neighbours of every test row. |
| `feature_times(df)` | `ml_feature_timestamps` | `fail` when a feature value is stamped after the decision that uses it. |
| `features(df)` + `labels(df)` | `ml_feature_significance` | Permutation test: the label is circularly shifted at random (autocorrelation kept), rank correlation of each feature is compared with that null, Bonferroni-adjusted. `warn` when no feature beats it. |
| `features(df)` + `labels(df)` | `ml_importance_stability` | The information coefficient of the best feature in five time folds; `warn` when its sign agrees in fewer than 70 % of folds. |
| `features(df)` | `ml_feature_drift` | PSI per feature, with the Kolmogorov-Smirnov statistic in the details. |
| `LABEL_HORIZON > 1` or `label_spans(df)` | `ml_label_uniqueness` | Mean uniqueness of overlapping labels (Lopez de Prado); `warn` below 0.5, with the effective number of independent samples. |
| `predict_proba(model, df)` | `ml_calibration` | Brier score against the base-rate Brier, skill, and a reliability table; `warn` when there is no skill or the expected calibration error exceeds 0.10. Probabilities come from the same walk-forward as the positions. |
| `N_CONFIGS = 40` | `ml_trials_accounting` | Configurations tried. The Deflated Sharpe counts `max(n_trials, N_CONFIGS)`; `warn` when `n_trials` was lower. |

Three more lint rules cover code written inside `signal(df)`: `fit_on_test` (a scaler or model fitted on a `*_test` part),
`tune_on_test` (candidates scored on the test part, best one kept) and `cv_not_time_ordered` (`cv=5` in a
cross-validation helper). Hyper-parameter choices belong on a validation block inside the training period.

Two lint rules flag the classic leaks of machine-learning code written inside `signal(df)`: `full_sample_transform` (a
scaler, PCA or feature selector fitted on all rows before any split) and `target_encoding_full` (a mean of the target
over all rows mapped back to the features). Both are warnings: the protocol above is the real fix.

The constants are part of the strategy source, so they are hashed into the certificate. Setting `LABEL_HORIZON` or
`EMBARGO` lower than the truth weakens the test, and anyone who reads the source can see it.

## Events joined by publication time

Earnings surprises, news sentiment, alternative data and LLM outputs reach a strategy as events. The common leak is a join
on the event's own time (the quarter end, the moment the fact happened) instead of the time it was published.

```bash
monte-neo verify --ohlcv data.csv --strategy s.py --events events.csv [--events-delay 3600]
```

`events.csv` has `published_at` (required), `event_time` (optional), `symbol` (for universes) and numeric value columns.
The verifier joins them to the bars as `ev_<column>` columns, and the strategy reads those.

- An event is visible from the first bar that **opens after** `published_at + delay`. A bar that was already open when the
  news came out could not have used it.
- Nothing is filled before the first event.

| Check | What it says |
|-------|--------------|
| `events_quality` | Events published before they happened, a zero publication delay (is `published_at` really the publication time?), events outside the price range |
| `pit_events` | The same strategy run once more on a join by `event_time`. A warning when that join earns more than twice as much and 5 points more: most of the edge would need knowing events before they were public. |

The events go into the certificate as a hash and a delay. Recheck with the same file:
`monte-neo verify --recheck cert.json --ohlcv data.csv --strategy s.py --events events.csv`.

Not investment advice: a research example, not a call to trade or a promise of profit. Simulated results do not
predict future returns.
