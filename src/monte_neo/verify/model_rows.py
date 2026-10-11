"""Check rows of the ``fit`` / ``predict`` protocol, computed next to the verified walk-forward run."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.events_run import net_result
from monte_neo.verify.model_protocol import (
    ModelSignal,
    cv_overlap_row,
    feature_drift_row,
    psi,
    refit_gap_row,
    seed_stability_row,
)


def model_rows(df: pd.DataFrame, fn: ModelSignal, model: ExecutionModel, positions: str) -> list[dict[str, Any]]:
    """``ml_refit_gap`` (walk-forward against the whole-file fit) and, when the strategy defines ``cv_splits(df)``,
    ``ml_cv_overlap``; ``ml_seed_stability`` with ``SEEDS >= 2`` and ``ml_feature_drift`` with ``features``."""
    walk_forward = net_result(df, fn, model, positions)
    in_sample = net_result(df, None, model, positions, values=fn.in_sample(df))
    rows = [refit_gap_row(walk_forward, in_sample, fn.params)]
    if callable(fn.cv_splits):
        splits = list(fn.cv_splits(df.copy()))
        rows.append(cv_overlap_row(splits, fn.params["LABEL_HORIZON"], fn.params["EMBARGO"]))
    if fn.seeds >= 2:
        rows.append(seed_stability_row([net_result(df, fn.with_seed(k), model, positions) for k in range(fn.seeds)]))
    if callable(fn.features):
        row = _drift_row(df, fn)
        if row is not None:
            rows.append(row)
    return rows


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
    return feature_drift_row(values, cut, len(df))


__all__ = ["model_rows"]
