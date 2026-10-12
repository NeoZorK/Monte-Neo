"""A machine-learning strategy in the fit/predict protocol: the verifier decides what the model may learn from.

The model is a ridge regression (numpy only) on lagged returns. ``verify_strategy`` refits it walk-forward and compares
that with a fit on the whole file (the ``ml_refit_gap`` row). A LightGBM model drops into ``fit`` the same way: return
the fitted booster from ``fit`` and call ``booster.predict`` in ``predict``.

Run: uv run python examples/ml_fit_predict.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.disclaimer import SHORT
from monte_neo.verify import verify_strategy

REFIT_EVERY = 100  # bars between refits
MIN_TRAIN = 500  # bars before the first prediction
LABEL_HORIZON = 1  # the label is the next bar's return
EMBARGO = 5  # bars dropped between training rows and the first predicted row
LAGS = 5
RIDGE = 10.0


def _features(df: pd.DataFrame) -> np.ndarray:
    ret = np.log(df["close"]).diff().fillna(0.0)
    return np.column_stack([ret.shift(k).fillna(0.0).to_numpy() for k in range(LAGS)])


def fit(train: pd.DataFrame) -> np.ndarray:
    """Ridge weights from lagged returns to the next bar's return; sees only the rows the verifier allows."""
    x = _features(train)[:-1]
    y = np.diff(np.log(train["close"].to_numpy()))
    return np.linalg.solve(x.T @ x + RIDGE * np.eye(LAGS), x.T @ y)


def predict(model: np.ndarray, df: pd.DataFrame) -> np.ndarray:
    """One position per row: the sign of the predicted next return, flat when it is tiny."""
    pred = _features(df) @ model
    return np.where(np.abs(pred) > 0.0001, np.sign(pred), 0.0)


def make_bars(n: int = 4000, seed: int = 7, phi: float = 0.1) -> pd.DataFrame:
    """Hourly bars whose returns carry a weak AR(1) momentum, so a lagged-return model has something to find."""
    rng = np.random.default_rng(seed)
    ret = np.zeros(n)
    for i in range(1, n):
        ret[i] = phi * ret[i - 1] + rng.normal(0.0, 0.01)
    close = 100.0 * np.exp(np.cumsum(ret))
    open_ = np.r_[close[0], close[:-1]]
    spread = np.abs(rng.normal(0.0, 0.002, n))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2022-01-03", periods=n, freq="h"),
            "open": open_,
            "high": np.maximum(open_, close) * (1 + spread),
            "low": np.minimum(open_, close) * (1 - spread),
            "close": close,
            "volume": 1000.0,
        }
    )


if __name__ == "__main__":
    bars = make_bars()
    report = verify_strategy(bars, strategy=__file__, n_trials=5)
    print(f"verdict: {report['verdict']}  certificate {report['certificate_id']}")
    for row in report["checks"]:
        if row["id"] == "ml_refit_gap":
            print(f"  {row['id']:14s} {row['status']:5s} {row['summary']}")
    print(SHORT)
