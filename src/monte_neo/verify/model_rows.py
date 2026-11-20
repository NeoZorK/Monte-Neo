"""Check rows of the ``fit`` / ``predict`` protocol, computed next to the verified walk-forward run."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.events_run import net_result
from monte_neo.verify.ml_checks import (
    calibration_row,
    cv_shuffle_row,
    feature_significance_row,
    feature_timestamps_row,
    importance_stability_row,
    ks_statistic,
    label_uniqueness_row,
    trials_accounting_row,
)
from monte_neo.verify.model_protocol import (
    ModelSignal,
    cv_overlap_row,
    feature_drift_row,
    psi,
    refit_gap_row,
    seed_stability_row,
)


def model_rows(df: pd.DataFrame, fn: ModelSignal, model: ExecutionModel, positions: str, n_trials: int | None = None) -> list[dict[str, Any]]:
    """``ml_refit_gap`` (walk-forward against the whole-file fit) and, when the strategy defines ``cv_splits(df)``,
    ``ml_cv_overlap`` and ``ml_cv_shuffle``; ``ml_seed_stability`` with ``SEEDS >= 2``; ``ml_feature_drift`` with ``features``;
    the optional hooks of :mod:`monte_neo.verify.ml_checks` add the leakage, significance, calibration and trial rows."""
    walk_forward = net_result(df, fn, model, positions)
    in_sample = net_result(df, None, model, positions, values=fn.in_sample(df))
    rows = [refit_gap_row(walk_forward, in_sample, fn.params)]
    if callable(fn.cv_splits):
        splits = list(fn.cv_splits(df.copy()))
        rows.append(cv_overlap_row(splits, fn.params["LABEL_HORIZON"], fn.params["EMBARGO"]))
        rows.append(cv_shuffle_row(splits))
    if fn.seeds >= 2:
        rows.append(seed_stability_row([net_result(df, fn.with_seed(k), model, positions) for k in range(fn.seeds)]))
    if callable(fn.features):
        row = _drift_row(df, fn)
        if row is not None:
            rows.append(row)
        rows.extend(_feature_rows(df, fn))
    rows.extend(_label_rows(df, fn))
    if callable(fn.feature_times):
        rows.append(feature_timestamps_row(_decision_times(df), dict(pd.DataFrame(fn.feature_times(df.copy())).items())))
    if callable(fn.predict_proba):
        rows.append(_calibration_row(df, fn))
    if fn.n_configs:
        rows.append(trials_accounting_row(fn.n_configs, n_trials))
    return rows


def _decision_times(df: pd.DataFrame) -> Any:
    col = next((c for c in ("timestamp", "time", "datetime", "date") if c in df.columns), None)
    return df[col] if col else pd.Series(np.arange(len(df), dtype=np.float64))


def _numeric(frame: Any, n: int, hook: str) -> pd.DataFrame:
    out = pd.DataFrame(frame)
    if len(out) != n:
        raise ValueError(f"{hook}(df) must return one row per row of df: got {len(out)} for {n} rows")
    return out.apply(pd.to_numeric, errors="coerce")


def _feature_rows(df: pd.DataFrame, fn: ModelSignal) -> list[dict[str, Any]]:
    """``ml_feature_significance`` and ``ml_importance_stability``: ``features(df)`` against ``labels(df)`` on the predicted rows."""
    if not callable(fn.labels):
        return []
    cut = fn.params["MIN_TRAIN"]
    if cut >= len(df) - 1:
        return []
    feats = _numeric(fn.features(df.copy()), len(df), "features")
    label = _numeric(pd.Series(fn.labels(df.copy())), len(df), "labels").iloc[:, 0].to_numpy(np.float64)[cut:]
    cols = {str(c): feats[c].to_numpy(np.float64)[cut:] for c in feats.columns}
    return [feature_significance_row(cols, label), importance_stability_row(cols, label)]


def _label_rows(df: pd.DataFrame, fn: ModelSignal) -> list[dict[str, Any]]:
    """``ml_label_uniqueness`` when the strategy declares ``label_spans(df)`` or a ``LABEL_HORIZON`` above one bar."""
    if callable(fn.label_spans):
        starts, ends = fn.label_spans(df.copy())
        return [label_uniqueness_row(len(df), fn.params["LABEL_HORIZON"], (starts, ends))]
    if fn.params["LABEL_HORIZON"] > 1:
        return [label_uniqueness_row(len(df), fn.params["LABEL_HORIZON"])]
    return []


def _calibration_row(df: pd.DataFrame, fn: ModelSignal) -> dict[str, Any]:
    """``ml_calibration``: walk-forward probabilities against whether the next ``max(LABEL_HORIZON, 1)`` bars rose."""
    prob = fn.proba(df)
    if callable(fn.labels):
        lab = _numeric(pd.Series(fn.labels(df.copy())), len(df), "labels").iloc[:, 0].to_numpy(np.float64)
        outcome = np.where(np.isfinite(lab), (lab > 0).astype(np.float64), np.nan)
    else:
        h = max(fn.params["LABEL_HORIZON"], 1)
        close = df["close"].to_numpy(np.float64)
        fwd = np.full(len(df), np.nan)
        fwd[:-h] = close[h:] / close[:-h] - 1.0
        outcome = np.where(np.isfinite(fwd), (fwd > 0).astype(np.float64), np.nan)
    return calibration_row(prob, outcome)


def _drift_row(df: pd.DataFrame, fn: ModelSignal) -> dict[str, Any] | None:
    """``ml_feature_drift``: PSI of each ``features(df)`` column, first ``MIN_TRAIN`` rows against the rest."""
    feats = pd.DataFrame(fn.features(df.copy()))
    cut = fn.params["MIN_TRAIN"]
    if len(feats) != len(df):
        raise ValueError(f"features(df) must return one row per row of df: got {len(feats)} for {len(df)} rows")
    if cut >= len(df) - 1:
        return None
    num = feats.apply(pd.to_numeric, errors="coerce")
    values = {str(c): psi(num[c].to_numpy(np.float64)[:cut], num[c].to_numpy(np.float64)[cut:]) for c in num.columns}
    ks = {str(c): ks_statistic(num[c].to_numpy(np.float64)[:cut], num[c].to_numpy(np.float64)[cut:]) for c in num.columns}
    return feature_drift_row(values, cut, len(df), ks)


__all__ = ["model_rows"]
