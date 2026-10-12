"""ml_seed_stability and ml_feature_drift: extras of the fit / predict protocol."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify import verify_strategy
from monte_neo.verify.ingest import load_signal_fn
from monte_neo.verify.model_protocol import NEXT_ACTIONS, ModelSignal, feature_drift_row, psi, seed_stability_row

BASE = '''
import numpy as np

REFIT_EVERY = 100
MIN_TRAIN = 300
LABEL_HORIZON = 1
EMBARGO = 2
'''

DETERMINISTIC = BASE + '''
SEEDS = 3


def fit(train, seed=0):
    r = train["close"].pct_change().to_numpy()
    x, y = r[1:-1], r[2:]
    ok = np.isfinite(x) & np.isfinite(y)
    return float(np.polyfit(x[ok], y[ok], 1)[0])


def predict(beta, df):
    return np.sign(beta * df["close"].pct_change().fillna(0.0).to_numpy())
'''

# The seed picks the sign of the bet: a coin flip dressed as a model.
SEED_SENSITIVE = DETERMINISTIC.replace(
    "return float(np.polyfit(x[ok], y[ok], 1)[0])",
    "return float(np.polyfit(x[ok], y[ok], 1)[0]) * (1.0 if seed % 2 == 0 else -1.0)",
)

FEATURES = '''

def features(df):
    r = df["close"].pct_change().fillna(0.0)
    scale = np.where(np.arange(len(df)) < 800, 1.0, 4.0)
    return __import__("pandas").DataFrame({"ret": r, "shifted": r * scale + np.where(np.arange(len(df)) < 800, 0.0, 0.05)})
'''


@pytest.fixture(scope="module")
def data() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    n = 1500
    r = np.zeros(n)
    e = rng.normal(0, 0.01, n)
    for t in range(1, n):
        r[t] = 0.15 * r[t - 1] + e[t]
    close = 100 * np.exp(np.cumsum(r))
    op = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"timestamp": pd.date_range("2019-01-01", periods=n, freq="D"), "open": op,
                         "high": np.maximum(op, close) * 1.001, "low": np.minimum(op, close) * 0.999, "close": close})


def _rows(tmp_path: Path, text: str, data: pd.DataFrame) -> dict[str, dict]:
    path = tmp_path / "m.py"
    path.write_text(text, encoding="utf-8")
    report = verify_strategy(data, strategy=str(path), probe_checks=4, min_trades=10)
    return {c["id"]: c for c in report["checks"]}


def test_seed_sensitive_model_warns(tmp_path: Path, data: pd.DataFrame) -> None:
    row = _rows(tmp_path, SEED_SENSITIVE, data)["ml_seed_stability"]
    assert row["status"] == "warn" and row["details"]["seeds"] == 3
    assert row["details"]["min"] < 0 < row["details"]["max"]


def test_deterministic_model_passes(tmp_path: Path, data: pd.DataFrame) -> None:
    rows = _rows(tmp_path, DETERMINISTIC, data)
    assert rows["ml_seed_stability"]["status"] == "pass", rows["ml_seed_stability"]["summary"]
    assert rows["ml_seed_stability"]["details"]["max"] == rows["ml_seed_stability"]["details"]["min"]


def test_without_seeds_or_features_rows_are_skipped(tmp_path: Path, data: pd.DataFrame) -> None:
    rows = _rows(tmp_path, DETERMINISTIC.replace("SEEDS = 3", ""), data)
    assert "ml_seed_stability" not in rows and "ml_feature_drift" not in rows
    rows = _rows(tmp_path, DETERMINISTIC.replace("seed=0", "").replace("train, )", "train)"), data)
    assert "ml_seed_stability" not in rows  # fit takes no seed


def test_default_call_is_unchanged_by_seeds(tmp_path: Path, data: pd.DataFrame) -> None:
    (tmp_path / "a.py").write_text(DETERMINISTIC, encoding="utf-8")
    (tmp_path / "b.py").write_text(DETERMINISTIC.replace("SEEDS = 3", ""), encoding="utf-8")
    fa, _ = load_signal_fn(str(tmp_path / "a.py"))
    fb, _ = load_signal_fn(str(tmp_path / "b.py"))
    assert isinstance(fa, ModelSignal) and fa.seeds == 3 and fb.seeds == 0
    assert np.array_equal(fa(data), fb(data)) and np.array_equal(fa.with_seed(0)(data), fa(data))


def test_feature_with_regime_shift_warns(tmp_path: Path, data: pd.DataFrame) -> None:
    rows = _rows(tmp_path, DETERMINISTIC + FEATURES, data)
    row = rows["ml_feature_drift"]
    assert row["status"] == "warn", row["summary"]
    assert row["details"]["top"][0]["feature"] == "shifted" and row["details"]["psi"]["shifted"] > 0.25


def test_stable_features_are_info(tmp_path: Path, data: pd.DataFrame) -> None:
    stable = '\n\ndef features(df):\n    return df["close"].pct_change().fillna(0.0).to_frame("ret")\n'
    row = _rows(tmp_path, DETERMINISTIC + stable, data)["ml_feature_drift"]
    assert row["status"] == "info" and row["details"]["psi"]["ret"] < 0.25


def test_psi_and_rows() -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(size=2000)
    assert psi(a, rng.normal(size=2000)) < 0.05
    assert psi(a, rng.normal(2.0, 1.0, size=2000)) > 0.25
    assert feature_drift_row({"x": 0.1, "y": 0.3}, 100, 300)["status"] == "warn"
    assert seed_stability_row([{"total_return": 0.2, "sharpe": 1.0}, {"total_return": 0.3, "sharpe": 1.1}])["status"] == "pass"
    assert seed_stability_row([{"total_return": 0.2, "sharpe": 1.0}, {"total_return": 0.1, "sharpe": 0.2}])["status"] == "warn"
    assert {"ml_seed_stability", "ml_feature_drift"} <= set(NEXT_ACTIONS)
