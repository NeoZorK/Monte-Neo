"""Machine-learning validation rows: cross-validation protocol, leakage and honesty checks for ``fit`` / ``predict`` models.

Every function here is pure (arrays in, one certificate row out) and deterministic: random permutations use a fixed seed.
The optional hooks a strategy file may define, each activating one row (see ``model_rows``):

* ``cv_splits(df)``      -> ``ml_cv_overlap`` (purge / embargo) and ``ml_cv_shuffle`` (scattered test folds).
* ``features(df)``       -> ``ml_feature_drift`` (PSI, KS); with ``labels(df)`` also ``ml_feature_significance``
  (permutation test) and ``ml_importance_stability`` (per-fold information coefficient).
* ``feature_times(df)``  -> ``ml_feature_timestamps``: a feature stamped later than the decision it feeds.
* ``labels(df)``         -> labels aligned with the bars; ``LABEL_HORIZON`` gives their reach.
* ``label_spans(df)``    -> ``ml_label_uniqueness`` for event labels (start, end bar of each label).
* ``predict_proba(model, df)`` -> ``ml_calibration``: Brier score and reliability of the probabilities.
* ``N_CONFIGS``          -> ``ml_trials_accounting``: configurations tried, counted into ``n_trials``.

``purged_kfold_splits`` and ``cpcv_splits`` build the honest splits a strategy can return from ``cv_splits``.
"""

from __future__ import annotations

from itertools import combinations
from math import comb
from typing import Any

import numpy as np

from monte_neo.verify.checks import check

MIN_RUN_LENGTH = 5.0        # a test fold made of runs shorter than this on average is scattered over time
UNIQUENESS_WARN = 0.5       # mean label uniqueness below this: the labels overlap so much that rows are not independent
BRIER_BINS = 10
ECE_WARN = 0.10
PERMUTATIONS = 499
SIGNIFICANCE = 0.05
MIN_SIGNIFICANCE_ROWS = 60
STABILITY_FOLDS = 5
SIGN_AGREEMENT_WARN = 0.7
PERM_SEED = 20260101


def _contiguous_groups(n: int, groups: int) -> list[np.ndarray]:
    return [g for g in np.array_split(np.arange(n, dtype=np.int64), groups) if g.size]


def _purge(train: np.ndarray, tests: list[np.ndarray], label_horizon: int, embargo: int) -> np.ndarray:
    """Drop training rows whose label reaches a test block, or that sit inside the embargo after one."""
    keep = np.ones(train.size, dtype=bool)
    for block in tests:
        s, e = int(block.min()), int(block.max())
        keep &= ~((train >= s - label_horizon) & (train <= e + embargo))
    return train[keep]


def purged_kfold_splits(n: int, k: int = 5, label_horizon: int = 1, embargo: int = 0) -> list[tuple[np.ndarray, np.ndarray]]:
    """Purged K-fold with embargo for a time series of ``n`` rows (contiguous folds, no shuffling).

    A training row is dropped when its label (``label_horizon`` bars ahead) reaches into the test fold, or when it lies
    within ``embargo`` bars after the fold.

    Raises:
        ValueError: when ``k`` is below 2 or above ``n``, or a horizon / embargo is negative.
    """
    if k < 2 or k > n or label_horizon < 0 or embargo < 0:
        raise ValueError(f"purged_kfold_splits needs 2 <= k <= n and non-negative horizon/embargo, got n={n}, k={k}")
    everything = np.arange(n, dtype=np.int64)
    return [(_purge(everything, [test], label_horizon, embargo), test) for test in _contiguous_groups(n, k)]


def cpcv_splits(
    n: int, n_groups: int = 6, n_test_groups: int = 2, label_horizon: int = 1, embargo: int = 0
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Combinatorial purged cross-validation: every choice of ``n_test_groups`` of ``n_groups`` blocks is a test set.

    The number of splits is ``C(n_groups, n_test_groups)``; they rebuild ``C(n_groups - 1, n_test_groups - 1)``
    complete backtest paths (see :func:`cpcv_paths`).

    Raises:
        ValueError: on impossible group counts or a negative horizon / embargo.
    """
    if not 1 <= n_test_groups < n_groups <= n or label_horizon < 0 or embargo < 0:
        raise ValueError(f"cpcv_splits needs 1 <= n_test_groups < n_groups <= n, got n={n}, groups={n_groups}, test={n_test_groups}")
    blocks = _contiguous_groups(n, n_groups)
    everything = np.arange(n, dtype=np.int64)
    out = []
    for chosen in combinations(range(len(blocks)), n_test_groups):
        tests = [blocks[i] for i in chosen]
        out.append((_purge(everything, tests, label_horizon, embargo), np.concatenate(tests)))
    return out


def cpcv_paths(n_groups: int, n_test_groups: int) -> int:
    """Number of complete backtest paths a CPCV with these group counts rebuilds."""
    return comb(n_groups - 1, n_test_groups - 1)


def _runs(index: np.ndarray) -> int:
    return int(1 + np.sum(np.diff(np.sort(index)) > 1)) if index.size else 0


def cv_shuffle_row(splits: list[tuple[Any, Any]]) -> dict[str, Any]:
    """Row ``ml_cv_shuffle`` (category ``lookahead``): test folds scattered over time (shuffled K-fold on a time series).

    A test fold made of long contiguous blocks is a time split (purged K-fold, CPCV); one made of runs shorter than
    ``MIN_RUN_LENGTH`` rows on average is a random sample, so neighbours of every test row sit in the training set.
    """
    scattered = 0
    means: list[float] = []
    for _, test in splits:
        te = np.asarray(test, dtype=np.int64)
        if te.size == 0:
            continue
        mean_run = te.size / _runs(te)
        means.append(mean_run)
        scattered += int(mean_run < MIN_RUN_LENGTH and te.size >= MIN_RUN_LENGTH)
    details = {"splits": len(splits), "scattered_folds": scattered, "mean_run_length": round(float(np.mean(means)), 2) if means else 0.0,
               "min_run_length": MIN_RUN_LENGTH}
    if scattered:
        return check("ml_cv_shuffle", "lookahead", "warn",
                     f"{scattered} of {len(splits)} test folds are scattered over time (mean run {details['mean_run_length']} rows): "
                     "a shuffled K-fold trains on the neighbours of every test row", details)
    return check("ml_cv_shuffle", "lookahead", "pass", f"{len(splits)} test folds are contiguous blocks in time", details)


def feature_timestamps_row(decision: Any, feature_times: Any) -> dict[str, Any]:
    """Row ``ml_feature_timestamps`` (category ``lookahead``): feature values stamped after the decision that uses them.

    Args:
        decision: Decision time of each row (the bar time at which the position is taken), numeric or datetime-like.
        feature_times: ``{feature: time each value became known}`` aligned with ``decision``.
    """
    import pandas as pd

    def _stamps(values: Any) -> np.ndarray:
        s = pd.Series(values)
        if pd.api.types.is_numeric_dtype(s):
            return s.to_numpy(dtype=np.float64)
        return pd.to_datetime(s, utc=True, errors="coerce").astype("int64").to_numpy(dtype=np.float64)

    dec = _stamps(decision)
    late: dict[str, int] = {}
    for name, stamps in feature_times.items():
        known = _stamps(stamps)
        if known.size != dec.size:
            raise ValueError(f"feature_times['{name}'] has {known.size} rows, expected {dec.size}")
        count = int(np.sum(np.isfinite(known) & np.isfinite(dec) & (known > dec)))
        if count:
            late[str(name)] = count
    details = {"features": len(feature_times), "late_features": late}
    if late:
        worst = max(late, key=lambda k: late[k])
        return check("ml_feature_timestamps", "lookahead", "fail",
                     f"{len(late)} feature(s) carry values stamped after the decision that uses them ({worst}: {late[worst]} rows): "
                     "the model reads data that was not yet known", details)
    return check("ml_feature_timestamps", "lookahead", "pass", f"all {len(feature_times)} feature(s) were known by the decision time", details)


def label_uniqueness(starts: np.ndarray, ends: np.ndarray, n_bars: int) -> float:
    """Mean average-uniqueness of labels spanning bars ``[start, end]`` (inclusive) in a series of ``n_bars`` bars."""
    s = np.clip(np.asarray(starts, dtype=np.int64), 0, n_bars - 1)
    e = np.clip(np.asarray(ends, dtype=np.int64), 0, n_bars - 1)
    e = np.maximum(e, s)
    diff = np.zeros(n_bars + 1, dtype=np.float64)
    np.add.at(diff, s, 1.0)
    np.add.at(diff, e + 1, -1.0)
    concurrency = np.cumsum(diff)[:n_bars]
    inv = np.cumsum(np.concatenate([[0.0], 1.0 / np.maximum(concurrency, 1.0)]))
    return float(np.mean((inv[e + 1] - inv[s]) / (e - s + 1)))


def label_uniqueness_row(n_bars: int, label_horizon: int, spans: tuple[Any, Any] | None = None) -> dict[str, Any]:
    """Row ``ml_label_uniqueness`` (category ``statistics``): how much the training labels overlap in time.

    Without ``spans`` every bar carries a label reaching ``label_horizon`` bars ahead. Mean uniqueness 1 means
    independent labels; 0.2 means each label shares its bars with four others, so the effective sample is a fifth.
    """
    if spans is None:
        starts = np.arange(n_bars, dtype=np.int64)
        ends = starts + max(label_horizon, 1) - 1
    else:
        starts, ends = np.asarray(spans[0], dtype=np.int64), np.asarray(spans[1], dtype=np.int64)
    if starts.size == 0 or n_bars < 1:
        return check("ml_label_uniqueness", "statistics", "info", "no labels to assess", {"labels": 0})
    uniq = label_uniqueness(starts, ends, n_bars)
    effective = float(uniq * starts.size)
    details = {"mean_uniqueness": round(uniq, 4), "labels": int(starts.size), "effective_samples": round(effective, 1),
               "label_horizon": label_horizon, "warn_below": UNIQUENESS_WARN}
    text = f"mean label uniqueness {uniq:.2f}: {starts.size} labels carry about {effective:.0f} independent observations"
    if uniq < UNIQUENESS_WARN:
        return check("ml_label_uniqueness", "statistics", "warn", f"{text}; overlapping labels make rows near-copies of each other", details)
    return check("ml_label_uniqueness", "statistics", "pass", text, details)


def _ranks(x: np.ndarray) -> np.ndarray:
    return np.argsort(np.argsort(x, kind="stable"), kind="stable").astype(np.float64)


def _ic(feature: np.ndarray, label: np.ndarray) -> float:
    """Spearman rank correlation over the rows where both are finite (0 when undefined)."""
    ok = np.isfinite(feature) & np.isfinite(label)
    if ok.sum() < 3:
        return 0.0
    a, b = _ranks(feature[ok]), _ranks(label[ok])
    a, b = a - a.mean(), b - b.mean()
    den = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / den) if den > 0.0 else 0.0


def feature_significance_row(
    features: dict[str, np.ndarray], label: np.ndarray, permutations: int = PERMUTATIONS, seed: int = PERM_SEED
) -> dict[str, Any]:
    """Row ``ml_feature_significance`` (category ``statistics``): permutation test of each feature against the label.

    The label is circularly shifted by random offsets (keeps its autocorrelation, breaks its link to the feature), and
    the p-value of each feature's rank correlation is Bonferroni-adjusted over the features.
    """
    y = np.asarray(label, dtype=np.float64)
    rng = np.random.default_rng(seed)
    n = y.size
    if n < MIN_SIGNIFICANCE_ROWS or not features:
        return check("ml_feature_significance", "statistics", "info", f"too few rows ({n}) or no features for a permutation test", {"rows": n})
    shifts = rng.integers(max(1, n // 10), max(2, n - n // 10), size=permutations)
    out: dict[str, dict[str, float]] = {}
    for name, x in features.items():
        x = np.asarray(x, dtype=np.float64)
        obs = _ic(x, y)
        null = np.array([abs(_ic(x, np.roll(y, int(s)))) for s in shifts])
        p = float((1 + np.sum(null >= abs(obs))) / (1 + permutations))
        out[str(name)] = {"ic": round(obs, 4), "p_value": round(p, 4), "p_adjusted": round(min(1.0, p * len(features)), 4)}
    best = min(out, key=lambda k: out[k]["p_adjusted"])
    details = {"features": out, "permutations": permutations, "rows": n, "best": best, "alpha": SIGNIFICANCE}
    if out[best]["p_adjusted"] > SIGNIFICANCE:
        return check("ml_feature_significance", "statistics", "warn",
                     f"no feature beats a label shifted at random in time (best {best}: IC {out[best]['ic']:+.3f}, adjusted p {out[best]['p_adjusted']:.2f}): "
                     "the model's input carries no detectable signal", details)
    kept = sum(v["p_adjusted"] <= SIGNIFICANCE for v in out.values())
    return check("ml_feature_significance", "statistics", "pass",
                 f"{kept} of {len(out)} feature(s) beat the permutation null (best {best}: IC {out[best]['ic']:+.3f})", details)


def importance_stability_row(features: dict[str, np.ndarray], label: np.ndarray, folds: int = STABILITY_FOLDS) -> dict[str, Any]:
    """Row ``ml_importance_stability`` (category ``statistics``): does a feature work the same way in every time fold?

    Importance here is the rank information coefficient of the feature in each contiguous fold. The best feature (largest
    mean |IC|) should keep its sign in at least ``SIGN_AGREEMENT_WARN`` of the folds.
    """
    y = np.asarray(label, dtype=np.float64)
    n = y.size
    if n < folds * 20 or not features:
        return check("ml_importance_stability", "statistics", "info", f"too few rows ({n}) for {folds} folds", {"rows": n})
    cuts = np.array_split(np.arange(n), folds)
    table: dict[str, list[float]] = {name: [round(_ic(np.asarray(x, dtype=np.float64)[c], y[c]), 4) for c in cuts] for name, x in features.items()}
    best = max(table, key=lambda k: abs(float(np.mean(table[k]))))
    mean = float(np.mean(table[best]))
    agree = float(np.mean(np.sign(table[best]) == np.sign(mean))) if mean != 0.0 else 0.0
    details = {"folds": folds, "fold_ic": table, "best": best, "mean_ic": round(mean, 4), "sign_agreement": round(agree, 3),
               "warn_below": SIGN_AGREEMENT_WARN}
    text = f"best feature {best}: IC per fold {table[best]}, sign agrees in {agree:.0%} of folds"
    if agree < SIGN_AGREEMENT_WARN:
        return check("ml_importance_stability", "statistics", "warn", f"{text}: the importance flips between periods", details)
    return check("ml_importance_stability", "statistics", "pass", text, details)


def calibration_row(prob: np.ndarray, outcome: np.ndarray, bins: int = BRIER_BINS) -> dict[str, Any]:
    """Row ``ml_calibration`` (category ``statistics``): Brier score, skill against the base rate and reliability.

    Args:
        prob: Predicted probability of the event per row (values outside [0, 1] are rejected).
        outcome: 1 when the event happened, else 0.

    Raises:
        ValueError: when a probability lies outside [0, 1].
    """
    p, y = np.asarray(prob, dtype=np.float64), np.asarray(outcome, dtype=np.float64)
    ok = np.isfinite(p) & np.isfinite(y)
    p, y = p[ok], y[ok]
    if p.size < 30:
        return check("ml_calibration", "statistics", "info", f"too few probabilities ({p.size}) to assess calibration", {"rows": int(p.size)})
    if p.min() < 0.0 or p.max() > 1.0:
        raise ValueError("predict_proba must return probabilities within [0, 1]")
    brier = float(np.mean((p - y) ** 2))
    base = float(y.mean())
    ref = float(np.mean((base - y) ** 2))
    skill = 1.0 - brier / ref if ref > 0.0 else 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    curve, ece = [], 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            gap = abs(float(p[m].mean()) - float(y[m].mean()))
            ece += gap * float(m.mean())
            curve.append({"bin": b, "n": int(m.sum()), "mean_prob": round(float(p[m].mean()), 4), "frequency": round(float(y[m].mean()), 4)})
    details = {"brier": round(brier, 5), "brier_base_rate": round(ref, 5), "brier_skill": round(skill, 4), "ece": round(ece, 4),
               "rows": int(p.size), "base_rate": round(base, 4), "reliability": curve}
    text = f"Brier {brier:.4f} against {ref:.4f} for the base rate (skill {skill:+.3f}), expected calibration error {ece:.3f}"
    if skill <= 0.0:
        return check("ml_calibration", "statistics", "warn", f"{text}: the probabilities are no better than always predicting the base rate", details)
    if ece > ECE_WARN:
        return check("ml_calibration", "statistics", "warn", f"{text}: the probabilities are badly calibrated (reliability gap above {ECE_WARN})", details)
    return check("ml_calibration", "statistics", "pass", text, details)


def trials_accounting_row(declared_configs: int, n_trials: int | None) -> dict[str, Any]:
    """Row ``ml_trials_accounting`` (category ``statistics``): model configurations tried against the declared ``n_trials``.

    ``declared_configs`` is the strategy's ``N_CONFIGS``. The verifier counts ``max(n_trials, N_CONFIGS)`` into the
    Deflated Sharpe, so declaring fewer trials than configurations never lowers the haircut.
    """
    given = int(n_trials or 1)
    details = {"n_configs": int(declared_configs), "n_trials_declared": given, "n_trials_used": max(given, int(declared_configs))}
    if declared_configs > given:
        return check("ml_trials_accounting", "statistics", "warn",
                     f"the strategy declares {declared_configs} configurations but n_trials is {given}: "
                     f"{details['n_trials_used']} are counted into the Deflated Sharpe", details)
    return check("ml_trials_accounting", "statistics", "pass", f"n_trials {given} covers the {declared_configs} declared configurations", details)


def ks_statistic(train: np.ndarray, test: np.ndarray) -> float:
    """Two-sample Kolmogorov-Smirnov statistic (NaN ignored; 0 when either sample is empty)."""
    a, b = np.sort(train[np.isfinite(train)]), np.sort(test[np.isfinite(test)])
    if a.size == 0 or b.size == 0:
        return 0.0
    grid = np.concatenate([a, b])
    return float(np.max(np.abs(np.searchsorted(a, grid, side="right") / a.size - np.searchsorted(b, grid, side="right") / b.size)))


NEXT_ACTIONS = {
    "ml_cv_shuffle": "Test folds must be contiguous in time: use purged K-fold with an embargo, CPCV, or TimeSeriesSplit(gap=...) "
                     "(monte_neo.verify.ml_checks.purged_kfold_splits / cpcv_splits), never a shuffled K-fold.",
    "ml_feature_timestamps": "A feature is stamped after the decision that uses it: lag it by its publication delay and join on the time it "
                             "became known, not the time it describes.",
    "ml_label_uniqueness": "Labels overlap heavily: subsample the training rows every LABEL_HORIZON bars or weight them by uniqueness "
                           "(sequential bootstrap), and count the effective sample, not the row count.",
    "ml_feature_significance": "No feature beats a label shifted at random: the model is fitting noise. Remove features that do not pass a "
                               "permutation test, and do not tune the model until one does.",
    "ml_importance_stability": "The best feature changes sign between periods: its relation is regime-dependent. Report importance per fold, "
                               "drop unstable features, or add the regime to the model.",
    "ml_calibration": "The predicted probabilities are not probabilities: calibrate them on a held-out period (isotonic or Platt scaling) and "
                      "size positions from the calibrated value only.",
    "ml_trials_accounting": "Count every model configuration (hyper-parameters, feature sets, seeds picked by hand) into n_trials; "
                            "the Deflated Sharpe punishes the search, not the final model alone.",
}

__all__ = [
    "NEXT_ACTIONS", "calibration_row", "cpcv_paths", "cpcv_splits", "cv_shuffle_row", "feature_significance_row",
    "feature_timestamps_row", "importance_stability_row", "ks_statistic", "label_uniqueness", "label_uniqueness_row",
    "purged_kfold_splits", "trials_accounting_row",
]
