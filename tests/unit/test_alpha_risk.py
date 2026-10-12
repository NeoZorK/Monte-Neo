"""Family I: risk."""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.alpha.risk import NEXT_ACTIONS, concentration, run_risk, tail_risk

N = 1500
IDX = pd.bdate_range("2019-01-01", periods=N)


def _rows(**kw):
    rng = np.random.default_rng(0)
    m = rng.normal(0.0004, 0.01, N)
    r = rng.normal(0.0004, 0.01, N)
    return {x["id"]: x for x in run_risk(r, m, IDX, 252.0, **kw)}, r, m


def test_neutrality_declared_with_beta_warns() -> None:
    rng = np.random.default_rng(1)
    m = rng.normal(0, 0.01, N)
    r = 0.8 * m + rng.normal(0, 0.005, N)
    rows = {x["id"]: x for x in run_risk(r, m, IDX, 252.0, declared_neutral=True)}
    assert rows["neutrality"]["status"] == "warn"
    rows = {x["id"]: x for x in run_risk(r, m, IDX, 252.0)}
    assert rows["neutrality"]["status"] == "info"


def test_neutrality_passes_for_independent() -> None:
    w = np.random.default_rng(2).normal(size=(N, 10))
    w -= w.mean(axis=1, keepdims=True)
    rows, _, _ = _rows(weights=w, declared_neutral=True)
    assert rows["neutrality"]["status"] == "pass"


def test_concentrated_weights_warn() -> None:
    w = np.zeros((N, 10))
    w[:, 0], w[:, 1] = 0.7, -0.3
    row = concentration(w)
    assert row["status"] == "warn"
    assert row["details"]["max_weight"] > 0.25
    diversified = np.ones((N, 20)) / 20
    assert concentration(diversified)["status"] == "pass"


def test_no_weights_skips_weight_checks() -> None:
    rows, _, _ = _rows()
    assert rows["concentration"]["status"] == "skip"
    assert rows["leverage_gross_net"]["status"] == "skip"


def test_leverage_jump() -> None:
    w = np.ones((N, 4)) / 4
    w[700:] *= 3
    rows, _, _ = _rows(weights=w)
    assert abs(rows["leverage_gross_net"]["details"]["max_gross_jump"] - 2.0) < 1e-9


def test_stress_windows_found_on_2019_2023() -> None:
    rows, _, _ = _rows()
    wins = rows["historical_stress_replay"]["details"]["windows"]
    assert {"Covid", "Rates", "FTX", "SVB", "Crypto winter"} <= set(wins)
    assert "GFC" not in wins
    assert wins["Covid"]["bars"] > 15


def test_stress_skips_without_overlap() -> None:
    idx = pd.bdate_range("2016-01-01", periods=200)
    rng = np.random.default_rng(0)
    row = {x["id"]: x for x in run_risk(rng.normal(0, 0.01, 200), rng.normal(0, 0.01, 200), idx, 252.0)}
    assert row["historical_stress_replay"]["status"] == "skip"


def test_tail_risk_cvar_below_var() -> None:
    r = np.random.default_rng(0).standard_t(4, N) * 0.01
    d = tail_risk(r, IDX)["details"]
    assert d["cvar_95"] <= d["var_95"] and d["cvar_99"] <= d["var_99"]
    assert d["worst_bar"] <= d["cvar_99"]
    assert d["worst_month"] < 0 and d["longest_recovery_bars"] > 0 and d["longest_recovery_days"] > 0


def test_tail_risk_recovery_counts_open_drawdown() -> None:
    r = np.full(100, 0.001)
    r[10] = -0.1
    d = tail_risk(r)["details"]
    assert d["longest_recovery_bars"] >= 85


def test_next_actions_cover_ids() -> None:
    rows, _, _ = _rows(weights=np.ones((N, 20)) / 20)
    assert set(rows) == set(NEXT_ACTIONS)
