"""A11: machine-learning mistakes written with plain numpy (no framework needed) and their honest twins."""

from __future__ import annotations

import warnings

import numpy as np
import pytest
from zoo_lib import compile_signal, dataset, oracle_source

from monte_neo.verify import verify_strategy

DF = dataset(1200, seed=3)

PRELUDE = '''import numpy as np
import pandas as pd


def _features(df):
    c = df["close"]
    r = c.pct_change()
    return np.c_[r.fillna(0).to_numpy(), c.pct_change(5).fillna(0).to_numpy(), (c / c.rolling(20).mean() - 1).fillna(0).to_numpy()]


def _next_return(df):
    return df["close"].pct_change().shift(-1).fillna(0).to_numpy()


def _ols(X, y):
    A = np.c_[np.ones(len(X)), X]
    return np.linalg.lstsq(A, y, rcond=None)[0]


def _predict(w, X):
    return np.c_[np.ones(len(X)), X] @ w


def _kmeans(X, k=3, steps=12):
    centers = X[np.linspace(0, len(X) - 1, k).astype(int)].copy()
    for _ in range(steps):
        lab = np.argmin(((X[:, None, :] - centers[None]) ** 2).sum(2), axis=1)
        for j in range(k):
            if (lab == j).any():
                centers[j] = X[lab == j].mean(0)
    return centers


def _label(X, centers):
    return np.argmin(((X[:, None, :] - centers[None]) ** 2).sum(2), axis=1)


'''

# (id, body of signal(df), leaks)
CASES = [
    ("scaler_fit_on_all", """
X = _features(df)
Z = (X - X.mean(0)) / (X.std(0) + 1e-12)
return np.sign(Z[:, 1] - Z[:, 2])
""", True),
    ("pca_on_all", """
X = _features(df)
X = X - X.mean(0)
v = np.linalg.eigh(np.cov(X.T))[1][:, -1]
return np.sign(X @ v)
""", True),
    ("kmeans_on_all", """
X = _features(df)
lab = _label(X, _kmeans(X))
return np.where(lab == 0, 1, np.where(lab == 1, -1, 0))
""", True),
    ("ols_in_sample_on_next_return", """
X, y = _features(df), _next_return(df)
return np.sign(_predict(_ols(X, y), X))
""", True),
    ("random_split_train_on_the_future", """
X, y = _features(df), _next_return(df)
idx = np.random.default_rng(0).permutation(len(X))[: int(len(X) * 0.7)]
return np.sign(_predict(_ols(X[idx], y[idx]), X))
""", True),
    ("window_chosen_on_the_full_sample", """
c = df["close"]
best = max(range(5, 60, 5), key=lambda w: np.nansum(np.sign((c - c.rolling(w).mean()).to_numpy()[:-1]) * c.pct_change().to_numpy()[1:]))
return np.sign((c - c.rolling(best).mean()).fillna(0).to_numpy())
""", True),
    ("features_selected_by_future_correlation", """
X, y = _features(df), _next_return(df)
j = int(np.argmax([abs(np.corrcoef(X[:, k], y)[0, 1]) for k in range(X.shape[1])]))
return np.sign(X[:, j]) * np.sign(np.corrcoef(X[:, j], y)[0, 1])
""", True),
    ("overlapping_labels_without_purge", """
X = _features(df)
c = df["close"].to_numpy()
y = np.r_[c[20:] / c[:-20] - 1, np.zeros(20)]
out = np.zeros(len(X))
for t in range(100, len(X)):
    w = _ols(X[:t], y[:t])
    out[t] = np.sign(_predict(w, X[t : t + 1])[0])
return out
""", True),
    ("expanding_scaler", """
X = _features(df)
m = np.cumsum(X, 0) / np.arange(1, len(X) + 1)[:, None]
s = np.sqrt(np.maximum(np.cumsum(X**2, 0) / np.arange(1, len(X) + 1)[:, None] - m**2, 1e-12))
Z = (X - m) / s
return np.sign(Z[:, 1] - Z[:, 2])
""", False),
    ("walk_forward_ols_with_purge", """
X = _features(df)
c = df["close"].to_numpy()
y = np.r_[c[20:] / c[:-20] - 1, np.zeros(20)]
out = np.zeros(len(X))
for t in range(100, len(X)):
    w = _ols(X[: t - 20], y[: t - 20])
    out[t] = np.sign(_predict(w, X[t : t + 1])[0])
return out
""", False),
    ("rolling_pca", """
X = _features(df)
out = np.zeros(len(X))
for t in range(100, len(X)):
    win = X[t - 99 : t + 1]
    mu = win.mean(0)
    v = np.linalg.eigh(np.cov((win - mu).T))[1][:, -1]
    out[t] = np.sign((X[t] - mu) @ v)
return out
""", False),
    ("kmeans_on_the_burn_in_only", """
X = _features(df)
cut = 360
centers = _kmeans(X[:cut])
lab = _label(X, centers)
return np.where(np.arange(len(X)) < cut, 0, np.where(lab == 0, 1, np.where(lab == 1, -1, 0)))
""", False),
    ("ols_refit_every_50_bars_on_realised_labels", """
X = _features(df)
c = df["close"].to_numpy()
y = np.r_[c[1:] / c[:-1] - 1, 0.0]
out = np.zeros(len(X))
w = None
for t in range(100, len(X)):
    if (t - 100) % 50 == 0:
        w = _ols(X[: t - 1], y[: t - 1])
    out[t] = np.sign(_predict(w, X[t : t + 1])[0])
return out
""", False),
]


def _source(body: str) -> str:
    return PRELUDE + "def signal(df):\n" + "".join(f"    {line}\n" for line in body.strip().splitlines())


@pytest.mark.parametrize("case", CASES, ids=lambda c: c[0])
def test_ml_case(case: tuple) -> None:
    case_id, body, leaks = case
    src = _source(body)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert oracle_source(src, DF) == (not leaks), f"{case_id}: label disagrees with the oracle"
        report = verify_strategy(DF, signal_fn=compile_signal(src), source=src)
    status = {c["id"]: c["status"] for c in report["checks"]}
    caught = status.get("lookahead_truncation") == "fail" or status.get("lookahead_perturbation") == "fail"
    if leaks:
        assert caught, f"{case_id} leaks but was not caught: {status}"
    else:
        accused = [k for k in ("lookahead_truncation", "lookahead_perturbation", "external_data", "lookahead_static_lint", "determinism") if status.get(k) == "fail"]
        assert not accused, f"{case_id} is honest but was accused: {accused}"


def test_a_model_the_size_of_the_data_memorises_and_is_called_implausible_or_leaking() -> None:
    src = PRELUDE + """def signal(df):
    X, y = _features(df), _next_return(df)
    A = np.c_[np.ones(len(X)), X, X**2, X**3, np.sin(np.arange(len(X))[:, None] * np.arange(1, 400)[None] / 100.0)]
    w = np.linalg.lstsq(A, y, rcond=None)[0]
    return np.sign(A @ w)
"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        report = verify_strategy(DF, signal_fn=compile_signal(src), source=src)
    status = {c["id"]: c["status"] for c in report["checks"]}
    assert report["verdict"] == "REJECT" and (status["lookahead_truncation"] == "fail" or status["implausible_accuracy"] == "fail")
    assert not oracle_source(src, DF)
    _ = np
