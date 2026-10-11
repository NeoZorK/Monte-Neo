"""The ``fit`` / ``predict`` protocol: the verifier, not the strategy, decides what the model may learn from.

A machine-learning strategy usually fits its model inside ``signal(df)`` on the whole table. The look-ahead probes cannot
see that: a model fitted once on all rows still reacts to its input row by row. With this protocol the strategy file
defines two functions instead of ``signal``::

    def fit(train: pd.DataFrame) -> object: ...                  # sees only rows the verifier allows
    def predict(model: object, df: pd.DataFrame) -> positions: ...  # one value per row of df

and, optionally, the walk-forward schedule as module constants (part of the hashed source)::

    REFIT_EVERY = 63      # bars between refits
    MIN_TRAIN = 252       # bars before the first prediction
    LABEL_HORIZON = 1     # bars a training label looks ahead (the last labels are dropped: they need the future)
    EMBARGO = 5           # extra bars dropped between the training rows and the first predicted row

The verifier refits on rows ``[0, start - LABEL_HORIZON - EMBARGO)`` and predicts rows ``[start, start + REFIT_EVERY)``:
no prediction ever comes from a model that saw its own future. ``ml_refit_gap`` then compares that honest walk-forward
with the author's in-sample fit on the whole file (``predict(fit(df), df)``): when the profit exists only in-sample, it
lived in the fit, not in the market.
"""

from __future__ import annotations

import hashlib
import inspect
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check

DEFAULTS = {"REFIT_EVERY": 63, "MIN_TRAIN": 252, "LABEL_HORIZON": 1, "EMBARGO": 5}


class ModelSignal:
    """``signal(df)`` built from ``fit`` / ``predict`` with a verifier-controlled walk-forward."""

    def __init__(self, fit: Any, predict: Any, params: dict[str, int], cv_splits: Any = None, seed: int | None = None) -> None:
        """Keep the two functions and the schedule; fitted models are cached by their exact training rows.

        ``seed`` is passed to ``fit`` as ``seed=...`` when not ``None``; the default call (``None``) leaves ``fit`` untouched.
        ``seeds`` (``SEEDS`` of the module, 0 when absent) and ``features`` are filled in by :func:`from_module`.
        """
        self.fit, self.predict, self.params, self.cv_splits, self.seed = fit, predict, params, cv_splits, seed
        self.seeds: int = 0
        self.features: Any = None
        self._cache: dict[tuple[int, str], Any] = {}

    def _model(self, train: pd.DataFrame) -> Any:
        key = (len(train), hashlib.sha1(pd.util.hash_pandas_object(train, index=False).to_numpy().tobytes()).hexdigest())
        if key not in self._cache:
            if len(self._cache) > 256:
                self._cache.clear()
            self._cache[key] = self.fit(train.copy()) if self.seed is None else self.fit(train.copy(), seed=self.seed)
        return self._cache[key]

    def __call__(self, df: pd.DataFrame) -> np.ndarray:
        """Walk-forward positions: rows before ``MIN_TRAIN`` are flat; each block is predicted by a model fitted earlier."""
        p = self.params
        n = len(df)
        out = np.zeros(n, dtype=np.float64)
        gap = p["LABEL_HORIZON"] + p["EMBARGO"]
        for start in range(p["MIN_TRAIN"], n, p["REFIT_EVERY"]):
            end = min(start + p["REFIT_EVERY"], n)
            if start - gap < 2:
                continue
            model = self._model(df.iloc[: start - gap])
            pred = np.asarray(self.predict(model, df.iloc[:end].copy()), dtype=np.float64).reshape(-1)
            if pred.size != end:
                raise ValueError(f"predict(model, df) must return one value per row of df: got {pred.size} for {end} rows")
            out[start:end] = np.nan_to_num(pred[start:end])
        return out

    def with_seed(self, seed: int) -> ModelSignal:
        """The same model with ``fit(train, seed=seed)`` and its own cache (used by ``ml_seed_stability``)."""
        other = ModelSignal(self.fit, self.predict, self.params, self.cv_splits, seed=int(seed))
        other.seeds, other.features = self.seeds, self.features
        return other

    def in_sample(self, df: pd.DataFrame) -> np.ndarray:
        """The author's usual backtest: one model fitted on every row, predicting the same rows."""
        return np.asarray(self.predict(self.fit(df.copy()), df.copy()), dtype=np.float64).reshape(-1)


def from_module(module: Any) -> ModelSignal | None:
    """A :class:`ModelSignal` when the module defines ``fit`` and ``predict`` (and no ``signal``), else ``None``."""
    fit, predict = getattr(module, "fit", None), getattr(module, "predict", None)
    if not (callable(fit) and callable(predict)):
        return None
    params = {k: int(getattr(module, k, v)) for k, v in DEFAULTS.items()}
    if params["REFIT_EVERY"] < 1 or params["MIN_TRAIN"] < 2 or params["LABEL_HORIZON"] < 0 or params["EMBARGO"] < 0:
        raise ValueError(f"model protocol constants out of range: {params}")
    sig = ModelSignal(fit, predict, params, getattr(module, "cv_splits", None))
    seeds = getattr(module, "SEEDS", 0)
    sig.seeds = int(seeds) if isinstance(seeds, int | np.integer) and not isinstance(seeds, bool) and _takes_seed(fit) else 0
    sig.features = getattr(module, "features", None) if callable(getattr(module, "features", None)) else None
    return sig


def _takes_seed(fit: Any) -> bool:
    """True when ``fit`` accepts a ``seed`` keyword (named parameter or ``**kwargs``)."""
    try:
        params = inspect.signature(fit).parameters
    except (TypeError, ValueError):
        return False
    return "seed" in params or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def refit_gap_row(walk_forward: dict[str, float], in_sample: dict[str, float], params: dict[str, int]) -> dict[str, Any]:
    """Row ``ml_refit_gap`` (category ``lookahead``): honest walk-forward against the author's whole-file fit.

    Args:
        walk_forward: ``{"total_return", "sharpe"}`` of the verified walk-forward run.
        in_sample: The same for ``predict(fit(df), df)``.
        params: The walk-forward schedule.
    """
    wf, ins = walk_forward, in_sample
    details = {"walk_forward": wf, "in_sample": ins, "schedule": params}
    text = (f"Sharpe {ins['sharpe']:.2f} when the model is fitted on the whole file, {wf['sharpe']:.2f} when it is refitted "
            f"only on the past (every {params['REFIT_EVERY']} bars, embargo {params['EMBARGO']})")
    if ins["sharpe"] > 0.5 and wf["total_return"] <= 0.0:
        return check("ml_refit_gap", "lookahead", "fail", f"{text}: the profit lived in the fit, not in the market", details)
    if ins["sharpe"] > 0.5 and wf["sharpe"] < 0.5 * ins["sharpe"]:
        return check("ml_refit_gap", "lookahead", "warn", f"{text}: most of the in-sample edge does not survive refitting", details)
    return check("ml_refit_gap", "lookahead", "pass", f"{text}: the edge survives honest refitting", details)


def cv_overlap_row(splits: list[tuple[Any, Any]], label_horizon: int, embargo: int) -> dict[str, Any]:
    """Row ``ml_cv_overlap`` (category ``lookahead``): training rows whose labels reach into a test fold.

    A training row ``i`` before a test fold starting at ``s`` leaks when ``i + label_horizon >= s``; a training row after
    the fold ending at ``e`` leaks when ``i <= e + embargo`` (serial correlation carries the test period into it).
    """
    leaks = total = 0
    for train, test in splits:
        tr, te = np.asarray(train, dtype=np.int64), np.asarray(test, dtype=np.int64)
        if tr.size == 0 or te.size == 0:
            continue
        s, e = int(te.min()), int(te.max())
        before = tr[tr < s]
        after = tr[tr > e]
        inside = tr[(tr >= s) & (tr <= e)]
        leaks += int(np.sum(before + label_horizon >= s) + np.sum(after <= e + embargo) + inside.size)
        total += int(tr.size)
    details = {"splits": len(splits), "leaking_training_rows": leaks, "training_rows": total,
               "label_horizon": label_horizon, "embargo": embargo}
    if leaks:
        return check("ml_cv_overlap", "lookahead", "warn",
                     f"{leaks} training row(s) overlap a test fold within the label horizon or embargo: purge them", details)
    return check("ml_cv_overlap", "lookahead", "pass", f"{len(splits)} folds are purged and embargoed", details)


PSI_BINS = 10
PSI_WARN = 0.25
EPS = 1e-4


def seed_stability_row(results: list[dict[str, float]]) -> dict[str, Any]:
    """Row ``ml_seed_stability`` (category ``statistics``): the walk-forward repeated with seeds 0..k-1.

    Warns when the sign of the net Sharpe flips across seeds or when the spread (max - min) exceeds ``|median|``.

    Args:
        results: One ``{"total_return", "sharpe"}`` per seed, in seed order.
    """
    sh = np.array([r["sharpe"] for r in results], dtype=np.float64)
    positive = float(np.mean([r["total_return"] > 0.0 for r in results]))
    lo, med, hi = float(sh.min()), float(np.median(sh)), float(sh.max())
    details = {"seeds": len(results), "sharpes": [float(v) for v in sh], "min": lo, "median": med, "max": hi,
               "share_positive_net_return": positive}
    text = f"net Sharpe over {len(results)} seeds: min {lo:.2f}, median {med:.2f}, max {hi:.2f}; {positive:.0%} of seeds end positive"
    if lo <= 0.0 < hi or positive not in (0.0, 1.0):
        return check("ml_seed_stability", "statistics", "warn", f"{text}: the sign flips with the seed", details)
    if hi - lo > abs(med):
        return check("ml_seed_stability", "statistics", "warn", f"{text}: the seed moves the result by more than its median", details)
    return check("ml_seed_stability", "statistics", "pass", f"{text}: the result does not depend on the seed", details)


def psi(train: np.ndarray, test: np.ndarray, bins: int = PSI_BINS) -> float:
    """Population stability index of ``test`` against ``bins`` quantile bins of ``train`` (NaN values are ignored)."""
    a, b = train[np.isfinite(train)], test[np.isfinite(test)]
    if a.size < bins or b.size == 0:
        return 0.0
    edges = np.unique(np.quantile(a, np.linspace(0.0, 1.0, bins + 1)[1:-1]))
    pa = np.bincount(np.searchsorted(edges, a, side="right"), minlength=edges.size + 1) / a.size
    pb = np.bincount(np.searchsorted(edges, b, side="right"), minlength=edges.size + 1) / b.size
    pa, pb = np.maximum(pa, EPS), np.maximum(pb, EPS)
    return float(np.sum((pb - pa) * np.log(pb / pa)))


def feature_drift_row(values: dict[str, float], min_train: int, n_rows: int) -> dict[str, Any]:
    """Row ``ml_feature_drift`` (category ``statistics``): PSI of each feature, training part against out-of-sample rows.

    Args:
        values: PSI per feature name.
        min_train: Rows of the reference (training) part.
        n_rows: Total rows.
    """
    ranked = sorted(values.items(), key=lambda kv: -kv[1])
    top = [{"feature": k, "psi": round(v, 4)} for k, v in ranked[:3]]
    details = {"psi": {k: round(v, 4) for k, v in values.items()}, "top": top, "bins": PSI_BINS, "warn_above": PSI_WARN,
               "reference_rows": min_train, "oos_rows": n_rows - min_train}
    shown = ", ".join(f"{t['feature']} {t['psi']:.2f}" for t in top)
    if ranked and ranked[0][1] > PSI_WARN:
        return check("ml_feature_drift", "statistics", "warn", f"feature drift (PSI > {PSI_WARN}): {shown}: the model meets inputs it was not trained on", details)
    return check("ml_feature_drift", "statistics", "info", f"largest feature drift (PSI): {shown or 'none'}", details)


NEXT_ACTIONS = {
    "ml_seed_stability": "The result changes with the random seed: average several seeds or fix the model's randomness, "
                         "and report the median across seeds, not the best seed.",
    "ml_feature_drift": "Some inputs look different out-of-sample than in training (PSI above 0.25): check for a regime change "
                        "or a data change, make the features stationary (returns, ranks, z-scores), or refit more often.",
    "ml_refit_gap": "The model's profit comes from fitting on the whole file: judge it only by the walk-forward result, "
                    "reduce the model's freedom (fewer features, stronger regularisation), and keep LABEL_HORIZON and EMBARGO honest.",
    "ml_cv_overlap": "Purge training rows whose labels reach into a test fold and add an embargo after each fold "
                     "(purged K-fold, or TimeSeriesSplit with gap >= label horizon).",
}

__all__ = [
    "DEFAULTS", "NEXT_ACTIONS", "ModelSignal", "cv_overlap_row", "feature_drift_row", "from_module", "psi", "refit_gap_row",
    "seed_stability_row",
]
