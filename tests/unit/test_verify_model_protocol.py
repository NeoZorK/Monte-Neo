"""The fit / predict protocol: the verifier runs the walk-forward; a model whose profit lives in the fit is caught."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify import recheck_certificate, verify_strategy
from monte_neo.verify.ingest import load_signal_fn
from monte_neo.verify.model_protocol import ModelSignal, cv_overlap_row

HONEST = '''
import numpy as np

REFIT_EVERY = 100
MIN_TRAIN = 300
LABEL_HORIZON = 1
EMBARGO = 2


def fit(train):
    r = train["close"].pct_change().to_numpy()
    x, y = r[1:-1], r[2:]
    ok = np.isfinite(x) & np.isfinite(y)
    return float(np.polyfit(x[ok], y[ok], 1)[0])


def predict(beta, df):
    r = df["close"].pct_change().fillna(0.0).to_numpy()
    return np.sign(beta * r)
'''

MEMORISER = '''
import numpy as np

REFIT_EVERY = 100
MIN_TRAIN = 300


def fit(train):
    nxt = train["close"].shift(-1) / train["close"] - 1.0
    return dict(zip(train["timestamp"].astype(str), np.sign(nxt.fillna(0.0))))


def predict(memory, df):
    return np.array([memory.get(t, 0.0) for t in df["timestamp"].astype(str)])
'''

LEAKY_CV = HONEST + '''

def cv_splits(df):
    n = len(df)
    return [(list(range(0, n // 2)) + list(range(n // 2 + 50, n)), list(range(n // 2, n // 2 + 50)))]
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


def _write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_loader_builds_a_walk_forward(tmp_path: Path, data: pd.DataFrame) -> None:
    fn, _ = load_signal_fn(_write(tmp_path, "honest.py", HONEST))
    assert isinstance(fn, ModelSignal) and fn.params["REFIT_EVERY"] == 100
    pos = fn(data)
    assert np.all(pos[:300] == 0) and np.any(pos[300:] != 0)
    cut = fn(data.iloc[:800])
    assert np.array_equal(cut, pos[:800])  # causal: a shorter table gives the same past positions


def test_honest_model_survives_refitting(tmp_path: Path, data: pd.DataFrame) -> None:
    path = _write(tmp_path, "honest.py", HONEST)
    report = json.loads(json.dumps(verify_strategy(data, strategy=path, probe_checks=6,
                                                   model=None, min_trades=10)))
    rows = {c["id"]: c for c in report["checks"]}
    assert rows["ml_refit_gap"]["status"] == "pass", rows["ml_refit_gap"]["summary"]
    assert rows["lookahead_truncation"]["status"] == "pass"
    assert recheck_certificate(report, data, strategy=path)["reproduced"]


def test_memorising_model_is_caught(tmp_path: Path, data: pd.DataFrame) -> None:
    report = verify_strategy(data, strategy=_write(tmp_path, "memo.py", MEMORISER), probe_checks=6)
    row = next(c for c in report["checks"] if c["id"] == "ml_refit_gap")
    assert row["status"] == "fail" and report["verdict"] == "REJECT"
    assert row["details"]["in_sample"]["sharpe"] > 5 > row["details"]["walk_forward"]["sharpe"]
    assert any("walk-forward" in a for a in report["next_actions"])


def test_unpurged_cv_is_flagged(tmp_path: Path, data: pd.DataFrame) -> None:
    report = verify_strategy(data, strategy=_write(tmp_path, "cv.py", LEAKY_CV), probe_checks=4, min_trades=10)
    assert {c["id"]: c["status"] for c in report["checks"]}["ml_cv_overlap"] == "warn"


def test_cv_overlap_math() -> None:
    clean = cv_overlap_row([(range(0, 90), range(100, 150))], label_horizon=5, embargo=5)
    assert clean["status"] == "pass"
    dirty = cv_overlap_row([(list(range(0, 98)) + list(range(152, 200)), range(100, 150))], label_horizon=5, embargo=5)
    assert dirty["status"] == "warn" and dirty["details"]["leaking_training_rows"] == 3 + 3


def test_bad_constants(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="out of range"):
        load_signal_fn(_write(tmp_path, "bad.py", HONEST.replace("REFIT_EVERY = 100", "REFIT_EVERY = 0")))
