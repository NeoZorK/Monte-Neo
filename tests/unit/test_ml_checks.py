"""ML validation rows: purged K-fold / CPCV, leakage detectors, permutation significance, stability, calibration, trials."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from monte_neo.verify import verify_strategy
from monte_neo.verify.lint import lint_source
from monte_neo.verify.ml_checks import (
    calibration_row,
    cpcv_paths,
    cpcv_splits,
    cv_shuffle_row,
    feature_significance_row,
    feature_timestamps_row,
    importance_stability_row,
    ks_statistic,
    label_uniqueness,
    label_uniqueness_row,
    purged_kfold_splits,
    trials_accounting_row,
)
from monte_neo.verify.model_protocol import cv_overlap_row

# --- purged K-fold and CPCV -------------------------------------------------------------------------------------------------

def test_purged_kfold_has_no_overlap_and_contiguous_tests() -> None:
    splits = purged_kfold_splits(500, k=5, label_horizon=4, embargo=3)
    assert len(splits) == 5
    assert cv_overlap_row(splits, 4, 3)["status"] == "pass"
    assert cv_shuffle_row(splits)["status"] == "pass"
    covered = np.sort(np.concatenate([t for _, t in splits]))
    assert np.array_equal(covered, np.arange(500))  # every row is tested exactly once


def test_purged_kfold_without_purge_is_caught_by_overlap_row() -> None:
    naive = purged_kfold_splits(500, k=5, label_horizon=0, embargo=0)
    assert cv_overlap_row(naive, 4, 3)["status"] == "warn"


@pytest.mark.parametrize("n,k", [(10, 1), (10, 11), (0, 2)])
def test_purged_kfold_rejects_impossible_arguments(n: int, k: int) -> None:
    with pytest.raises(ValueError):
        purged_kfold_splits(n, k)


def test_cpcv_counts_and_paths() -> None:
    splits = cpcv_splits(600, n_groups=6, n_test_groups=2, label_horizon=2, embargo=2)
    assert len(splits) == 15 and cpcv_paths(6, 2) == 5
    assert cv_overlap_row(splits, 2, 2)["status"] == "pass"
    assert cv_shuffle_row(splits)["status"] == "pass"


@pytest.mark.parametrize("args", [(100, 3, 3), (100, 3, 0), (5, 6, 2)])
def test_cpcv_rejects_impossible_arguments(args: tuple[int, int, int]) -> None:
    with pytest.raises(ValueError):
        cpcv_splits(*args)


@settings(max_examples=40, deadline=None)
@given(n=st.integers(40, 400), k=st.integers(2, 8), h=st.integers(0, 6), e=st.integers(0, 6))
def test_purged_kfold_property_no_train_row_inside_purge_zone(n: int, k: int, h: int, e: int) -> None:
    for train, test in purged_kfold_splits(n, k, h, e):
        s, t = int(test.min()), int(test.max())
        assert not np.any((train >= s - h) & (train <= t + e))
        assert np.all(np.diff(test) == 1)


def test_shuffled_kfold_is_flagged_and_boundary_run_is_not() -> None:
    rng = np.random.default_rng(0)
    perm = rng.permutation(500)
    shuffled = [(perm[100:], np.sort(perm[:100]))]
    assert cv_shuffle_row(shuffled)["status"] == "warn"
    blocks = [(np.arange(50, 500), np.arange(0, 50))]
    assert cv_shuffle_row(blocks)["status"] == "pass"
    assert cv_shuffle_row([])["status"] == "pass"  # nothing to judge, nothing to accuse


# --- feature timestamps -----------------------------------------------------------------------------------------------------

def test_feature_timestamps_late_value_fails_and_equal_time_passes() -> None:
    dec = pd.date_range("2024-01-01", periods=10, freq="D")
    ok = feature_timestamps_row(dec, {"a": dec, "b": dec - pd.Timedelta(days=1)})
    assert ok["status"] == "pass"
    late = feature_timestamps_row(dec, {"a": dec, "b": dec + pd.Timedelta(hours=1)})
    assert late["status"] == "fail" and late["details"]["late_features"] == {"b": 10}


def test_feature_timestamps_numeric_and_length_mismatch() -> None:
    assert feature_timestamps_row(np.arange(5), {"f": np.arange(5) + 1})["status"] == "fail"
    with pytest.raises(ValueError, match="rows"):
        feature_timestamps_row(np.arange(5), {"f": np.arange(4)})


# --- label uniqueness -------------------------------------------------------------------------------------------------------

def test_label_uniqueness_values() -> None:
    n = 400
    assert label_uniqueness(np.arange(n), np.arange(n), n) == pytest.approx(1.0)
    row = label_uniqueness_row(n, 5)
    assert row["status"] == "warn" and row["details"]["mean_uniqueness"] < 0.5
    assert label_uniqueness_row(n, 1)["status"] == "pass"
    non_overlapping = (np.arange(0, n, 10), np.arange(0, n, 10) + 9)
    assert label_uniqueness_row(n, 10, non_overlapping)["status"] == "pass"
    assert label_uniqueness_row(0, 3)["status"] == "info"


@settings(max_examples=40, deadline=None)
@given(n=st.integers(20, 300), h=st.integers(1, 15))
def test_label_uniqueness_is_in_unit_interval_and_falls_with_horizon(n: int, h: int) -> None:
    u1 = label_uniqueness_row(n, h)["details"]["mean_uniqueness"]
    u2 = label_uniqueness_row(n, h + 1)["details"]["mean_uniqueness"]
    assert 0.0 < u1 <= 1.0 and u2 <= u1 + 1e-9


# --- permutation significance and stability ----------------------------------------------------------------------------------

def _series(n: int = 600, signal: float = 0.0, seed: int = 3) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    return x, signal * x + rng.normal(size=n)


def test_feature_significance_detects_real_and_noise_features() -> None:
    x, y = _series(signal=0.6)
    good = feature_significance_row({"x": x}, y)
    assert good["status"] == "pass" and good["details"]["features"]["x"]["p_value"] < 0.05
    noise, y2 = _series(signal=0.0, seed=9)
    bad = feature_significance_row({"x": noise}, y2)
    assert bad["status"] == "warn"


def test_feature_significance_is_deterministic_and_handles_small_input() -> None:
    x, y = _series(signal=0.3)
    assert feature_significance_row({"x": x}, y) == feature_significance_row({"x": x}, y)
    assert feature_significance_row({"x": x[:20]}, y[:20])["status"] == "info"
    assert feature_significance_row({}, y)["status"] == "info"


def test_feature_significance_ignores_nan_and_inf() -> None:
    x, y = _series(signal=0.6)
    x[::7] = np.nan
    y[::11] = np.inf
    assert feature_significance_row({"x": x}, y)["status"] == "pass"


def test_importance_stability_flags_a_sign_flip_and_passes_a_stable_feature() -> None:
    x, y = _series(n=1000, signal=0.5)
    assert importance_stability_row({"x": x}, y)["status"] == "pass"
    flipped = y.copy()
    flipped[:500] = -flipped[:500]
    row = importance_stability_row({"x": x}, flipped)
    assert row["status"] == "warn" or abs(row["details"]["mean_ic"]) < 0.1  # best feature flips between halves
    assert importance_stability_row({"x": x[:50]}, y[:50])["status"] == "info"


def test_importance_stability_warns_on_alternating_sign() -> None:
    x, y = _series(n=1000, signal=0.7)
    for i, cut in enumerate(np.array_split(np.arange(1000), 5)):
        if i % 2:
            y[cut] = -y[cut]
    assert importance_stability_row({"x": x}, y)["status"] == "warn"


# --- calibration -----------------------------------------------------------------------------------------------------------

def test_calibration_good_overconfident_and_uninformative() -> None:
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, 4000)
    y = (rng.uniform(size=4000) < p).astype(float)
    assert calibration_row(p, y)["status"] == "pass"
    sharp = np.where(p > 0.5, 0.99, 0.01)
    assert calibration_row(sharp, y)["status"] == "warn"
    assert calibration_row(np.full(4000, 0.5), y)["status"] == "warn"  # no skill over the base rate


def test_calibration_boundaries() -> None:
    assert calibration_row(np.array([0.5] * 10), np.ones(10))["status"] == "info"
    with pytest.raises(ValueError, match="within"):
        calibration_row(np.linspace(0, 1.5, 100), np.zeros(100))
    p = np.full(100, np.nan)
    assert calibration_row(p, np.zeros(100))["status"] == "info"


# --- trials accounting and KS ----------------------------------------------------------------------------------------------

def test_trials_accounting() -> None:
    assert trials_accounting_row(40, 3)["status"] == "warn"
    assert trials_accounting_row(40, 3)["details"]["n_trials_used"] == 40
    assert trials_accounting_row(10, 10)["status"] == "pass"
    assert trials_accounting_row(10, None)["details"]["n_trials_declared"] == 1


def test_ks_statistic() -> None:
    a = np.random.default_rng(1).normal(size=500)
    assert ks_statistic(a, a) == 0.0
    assert ks_statistic(a, a + 5) > 0.9
    assert ks_statistic(np.array([]), a) == 0.0
    assert ks_statistic(np.array([np.nan]), a) == 0.0


# --- lint rules -------------------------------------------------------------------------------------------------------------

def _lint(body: str) -> dict[str, str]:
    src = "import numpy as np\n\ndef signal(df):\n" + "".join(f"    {ln}\n" for ln in body.splitlines()) + "    return np.zeros(len(df))\n"
    return {f["rule"]: f["severity"] for f in lint_source(src)["findings"]}


@pytest.mark.parametrize("body", [
    "sc = StandardScaler().fit(X_test)",
    "sc = StandardScaler()\nsc.fit_transform(x_test)",
    "model.fit(X_test, y_test)",
    "model.partial_fit(df_test)",
])
def test_fit_on_test_flagged(body: str) -> None:
    assert _lint(body).get("fit_on_test") == "warn"


@pytest.mark.parametrize("body", [
    "model.fit(X_train, y_train)",
    "model.fit(X[:split], y[:split])",
    "model.fit(latest_rows)",
    "model.fit(contest)",
])
def test_fit_on_test_quiet_for_training_data(body: str) -> None:
    assert "fit_on_test" not in _lint(body)


def test_tune_on_test_flagged_and_validation_is_quiet() -> None:
    bad = "best = None\nfor n in (1, 2, 3):\n    s = model.score(X_test, y_test)\n    best = max(best or 0, s)"
    assert _lint(bad).get("tune_on_test") == "warn"
    good = "for n in (1, 2, 3):\n    s = model.score(X_val, y_val)\n    best = max(0, s)"
    assert "tune_on_test" not in _lint(good)
    no_pick = "for n in (1, 2, 3):\n    s = model.score(X_test, y_test)"
    assert "tune_on_test" not in _lint(no_pick)


@pytest.mark.parametrize("call,flagged", [
    ("cross_val_score(m, X, y, cv=5)", True),
    ("GridSearchCV(m, grid, cv=3)", True),
    ("cross_val_score(m, X, y, cv=TimeSeriesSplit(5, gap=3))", False),
    ("cross_val_score(m, X, y)", False),
])
def test_cv_integer_rule(call: str, flagged: bool) -> None:
    assert ("cv_not_time_ordered" in _lint(f"r = {call}")) is flagged


# --- end to end through verify_strategy -------------------------------------------------------------------------------------

MODEL = '''
import numpy as np
from monte_neo.verify.ml_checks import purged_kfold_splits
REFIT_EVERY = 100
MIN_TRAIN = 300
LABEL_HORIZON = 3
EMBARGO = 2
N_CONFIGS = 40
def fit(train):
    r = train["close"].pct_change().to_numpy(); x, y = r[1:-1], r[2:]; ok = np.isfinite(x) & np.isfinite(y)
    return float(np.polyfit(x[ok], y[ok], 1)[0])
def predict(b, df):
    r = df["close"].pct_change().fillna(0.0).to_numpy(); return np.sign(b * r)
def predict_proba(b, df):
    r = df["close"].pct_change().fillna(0.0).to_numpy(); return 1 / (1 + np.exp(-50 * b * r))
def features(df):
    return {"r1": df["close"].pct_change().fillna(0), "r5": df["close"].pct_change(5).fillna(0)}
def labels(df):
    return df["close"].shift(-3) / df["close"] - 1
def cv_splits(df):
    return purged_kfold_splits(len(df), 5, 3, 2)
def feature_times(df):
    return {"r1": df["timestamp"]}
'''


def _walk(n: int = 1200) -> pd.DataFrame:
    c = 100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.01, n)))
    return pd.DataFrame({"timestamp": pd.date_range("2020-01-01", periods=n, freq="D"), "open": c, "high": c * 1.005,
                         "low": c * 0.995, "close": c, "volume": 1e6})


def test_model_certificate_carries_every_ml_row(tmp_path: Path) -> None:
    path = tmp_path / "m.py"
    path.write_text(MODEL)
    rep = verify_strategy(_walk(), strategy=path, n_trials=3)
    rows = {c["id"]: c for c in rep["checks"] if c["id"].startswith("ml_")}
    assert {"ml_cv_overlap", "ml_cv_shuffle", "ml_feature_drift", "ml_feature_significance", "ml_importance_stability",
            "ml_label_uniqueness", "ml_feature_timestamps", "ml_calibration", "ml_trials_accounting"} <= set(rows)
    assert rows["ml_feature_timestamps"]["status"] == "pass" and rows["ml_cv_shuffle"]["status"] == "pass"
    assert rows["ml_trials_accounting"]["status"] == "warn"
    assert next(c for c in rep["checks"] if c["id"] == "deflated_sharpe")["details"]["n_trials"] == 40
    assert any("n_trials" in a or "configuration" in a for a in rep["next_actions"])


def test_model_with_late_features_and_shuffled_folds_is_flagged(tmp_path: Path) -> None:
    bad = MODEL.replace("return purged_kfold_splits(len(df), 5, 3, 2)",
                        "p = np.random.default_rng(0).permutation(len(df)); return [(p[240:], np.sort(p[:240]))]").replace(
        'return {"r1": df["timestamp"]}', 'return {"r1": df["timestamp"] + __import__("pandas").Timedelta(days=1)}')
    path = tmp_path / "bad.py"
    path.write_text(bad)
    rep = verify_strategy(_walk(), strategy=path, n_trials=50)
    st_ = {c["id"]: c["status"] for c in rep["checks"]}
    assert st_["ml_feature_timestamps"] == "fail" and st_["ml_cv_shuffle"] == "warn" and st_["ml_cv_overlap"] == "warn"
    assert st_["ml_trials_accounting"] == "pass"
