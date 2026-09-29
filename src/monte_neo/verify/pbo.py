"""Probability of Backtest Overfitting (PBO) by combinatorially symmetric cross-validation.

Bailey, Borwein, Lopez de Prado and Zhu (2015). A parameter search picks the combination with
the best Sharpe ratio in the sample. If that combination usually falls below the median out of
sample, the search is choosing noise. CSCV splits the time axis into ``S`` equal slices, and for
every way of putting half of them in "training" and half in "testing" it asks: where does the
combination that won in training rank in testing? The rank ``w`` (0..1) becomes the logit
``ln(w / (1 - w))``; PBO is the share of splits where the logit is at most zero.

No randomness: every split is enumerated, so the result is reproducible. Needs the per-bar
returns of every combination (``verify_grid`` already has them).
"""

from __future__ import annotations

import itertools
from typing import Any

import numpy as np

from monte_neo.verify.checks import check

SLICES = 16
MIN_COMBOS = 4
MIN_BARS_PER_SLICE = 4
WARN_AT = 0.5
LOGIT_BINS = 21
LOGIT_LIMIT = 4.0


def _sharpe_from_sums(total: np.ndarray, squares: np.ndarray, n: int) -> np.ndarray:
    mean = total / n
    var = np.maximum(squares / n - mean * mean, 0.0) * n / (n - 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(var > 1e-30, mean / np.sqrt(var), 0.0)


def pbo_cscv(returns: np.ndarray, *, slices: int = SLICES) -> dict[str, Any]:
    """PBO of a ``(combinations, bars)`` matrix of per-bar returns; ``{}`` when it cannot be computed."""
    r = np.asarray(returns, dtype=np.float64)
    if r.ndim != 2 or r.shape[0] < MIN_COMBOS or slices < 2 or slices % 2:
        return {}
    n_combos, bars = r.shape
    length = bars // slices
    if length < MIN_BARS_PER_SLICE:
        return {}
    r = r[:, : length * slices]
    if not np.isfinite(r).all():
        r = np.nan_to_num(r)  # a non-finite bar is no evidence
    r = r.reshape(n_combos, slices, length)
    total, squares = r.sum(axis=2).T, (r * r).sum(axis=2).T  # (slices, combos)
    splits = np.array(list(itertools.combinations(range(slices), slices // 2)))
    train = np.zeros((len(splits), slices))
    np.put_along_axis(train, splits, 1.0, axis=1)
    test = 1.0 - train
    n_half = length * (slices // 2)
    sr_train = _sharpe_from_sums(train @ total, train @ squares, n_half)
    sr_test = _sharpe_from_sums(test @ total, test @ squares, n_half)
    best = np.argmax(sr_train, axis=1)  # the combination a search would pick
    rows = np.arange(len(splits))
    chosen = sr_test[rows, best][:, None]
    below = (sr_test < chosen).sum(axis=1) + 0.5 * ((sr_test == chosen).sum(axis=1) - 1)
    rank = (below + 1.0) / (n_combos + 1.0)  # 0..1, higher is better
    logit = np.log(rank / (1.0 - rank))
    loss = (test @ total)[rows, best] <= 0.0
    edges = np.linspace(-LOGIT_LIMIT, LOGIT_LIMIT, LOGIT_BINS + 1)
    counts, _ = np.histogram(np.clip(logit, -LOGIT_LIMIT, LOGIT_LIMIT - 1e-9), bins=edges)
    return {
        "method": "CSCV",
        "combinations": int(n_combos),
        "slices": int(slices),
        "splits": int(len(splits)),
        "pbo": round(float(np.mean(logit <= 0.0)), 4),
        "prob_loss": round(float(np.mean(loss)), 4),
        "median_logit": round(float(np.median(logit)), 3),
        "logit_hist": {"limit": LOGIT_LIMIT, "counts": [int(c) for c in counts]},
    }


def pbo_row(info: dict[str, Any]) -> dict[str, Any]:
    """``pbo``: warn when the search's winner is as likely as not to be below the median on unseen data."""
    if not info:
        return check("pbo", "statistics", "skip", "PBO needs at least 4 combinations and 64 bars")
    pbo = info["pbo"]
    summary = (
        f"probability of backtest overfitting {pbo:.3f}: the best combination in training ranks below the median "
        f"in testing in {pbo:.0%} of {info['splits']:,} splits; its testing return is a loss in {info['prob_loss']:.0%}"
    )
    return check("pbo", "statistics", "warn" if pbo >= WARN_AT else "pass", summary, info)


__all__ = ["pbo_cscv", "pbo_row"]
