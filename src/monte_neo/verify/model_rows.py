"""Check rows of the ``fit`` / ``predict`` protocol, computed next to the verified walk-forward run."""

from __future__ import annotations

from typing import Any

import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.events_run import net_result
from monte_neo.verify.model_protocol import ModelSignal, cv_overlap_row, refit_gap_row


def model_rows(df: pd.DataFrame, fn: ModelSignal, model: ExecutionModel, positions: str) -> list[dict[str, Any]]:
    """``ml_refit_gap`` (walk-forward against the whole-file fit) and, when the strategy defines ``cv_splits(df)``,
    ``ml_cv_overlap``."""
    walk_forward = net_result(df, fn, model, positions)
    in_sample = net_result(df, None, model, positions, values=fn.in_sample(df))
    rows = [refit_gap_row(walk_forward, in_sample, fn.params)]
    if callable(fn.cv_splits):
        splits = list(fn.cv_splits(df.copy()))
        rows.append(cv_overlap_row(splits, fn.params["LABEL_HORIZON"], fn.params["EMBARGO"]))
    return rows


__all__ = ["model_rows"]
