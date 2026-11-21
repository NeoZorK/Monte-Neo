"""Alpha after beta: decomposition on buy & hold, the gate and its effect on the ARL."""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.readiness import readiness
from monte_neo.verify.alpha_beta import MIN_OBS, alpha_after_beta_row, alpha_beta, nw_regression
from monte_neo.verify.returns_dd import verify_returns


def _bench(n: int = 500, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.001, 0.02, n)


def test_regression_recovers_known_alpha_and_beta() -> None:
    b = _bench()
    noise = np.random.default_rng(1).normal(0, 0.002, b.size)
    reg = nw_regression(0.0005 + 0.8 * b + noise, b)
    assert abs(reg["beta"] - 0.8) < 0.02 and abs(reg["alpha"] - 0.0005) < 0.0003
    assert reg["r2"] > 0.9 and reg["lags"] == int(4 * (500 / 100) ** (2 / 9))


def test_pure_beta_is_flagged() -> None:
    b = _bench()
    r = 1.3 * b + np.random.default_rng(2).normal(0, 0.003, b.size)
    row = alpha_after_beta_row(r, b, 365)
    assert row["status"] == "warn" and "not significant" in row["summary"]
    d = row["details"]
    assert abs(d["beta"] - 1.3) < 0.05 and d["alpha_ci95_annual"][0] < 0 < d["alpha_ci95_annual"][1]
    assert d["beta_share"] > 0.8


def test_real_alpha_passes() -> None:
    b = _bench()
    r = 0.003 + 0.2 * b + np.random.default_rng(3).normal(0, 0.004, b.size)
    row = alpha_after_beta_row(r, b, 365)
    assert row["status"] == "pass" and row["details"]["alpha_ci95_annual"][0] > 0


def test_negative_alpha_warns_and_share_is_none_when_mean_not_positive() -> None:
    b = _bench()
    r = -0.003 + 0.5 * b + np.random.default_rng(4).normal(0, 0.004, b.size)
    row = alpha_after_beta_row(r, b, 365)
    assert row["status"] == "warn" and row["details"]["beta_share"] is None
    assert alpha_beta(r, b, 365)["alpha_annual"] < 0


def test_skip_boundaries() -> None:
    b = _bench(MIN_OBS - 1)
    assert alpha_after_beta_row(b * 2, b, 365)["status"] == "skip"
    b = _bench(MIN_OBS)
    assert alpha_after_beta_row(b * 2 + 0.001, b, 365)["status"] in ("pass", "warn")
    assert alpha_after_beta_row(b, np.zeros(MIN_OBS), 365)["status"] == "skip"
    assert alpha_after_beta_row(np.zeros(MIN_OBS), b, 365)["status"] == "skip"


def test_lengths_are_aligned_to_the_shorter() -> None:
    b = _bench(300)
    r = 2.0 * b[-200:] + np.random.default_rng(5).normal(0, 0.003, 200)
    assert alpha_after_beta_row(r, b, 365)["details"]["n"] == 200


def test_returns_path_uses_the_gate() -> None:
    idx = pd.date_range("2020-01-01", periods=400, freq="D")
    b = pd.Series(_bench(400), idx)
    pure = pd.Series(1.1 * b.to_numpy() + np.random.default_rng(6).normal(0, 0.003, 400), idx)
    rep = verify_returns(pure, benchmark=b)
    row = next(c for c in rep["checks"] if c["id"] == "benchmark_relation")
    assert row["status"] == "warn" and "up_capture" in row["details"] and "correlation" in row["details"]
    assert any("benchmark_relation" in x for x in rep["reasons"])
    few = verify_returns(pure, benchmark=b.iloc[:10])
    assert next(c for c in few["checks"] if c["id"] == "benchmark_relation")["status"] == "skip"
    flat = verify_returns(pure, benchmark=pd.Series(np.zeros(400), idx))
    assert next(c for c in flat["checks"] if c["id"] == "benchmark_relation")["status"] == "skip"


def _cert(status: str) -> dict:
    ids = ["data_integrity", "lookahead_truncation", "net_profitability", "cost_margin", "timing_significance", "selection_adjusted_sharpe", "residual_alpha",
           "hidden_short_volatility", "trial_ledger"]
    rows = [{"id": i, "status": "pass", "category": "x"} for i in ids]
    return {"checks": rows + [{"id": "alpha_after_beta", "status": status, "category": "statistics"}]}


def test_arl_blocked_at_five_when_alpha_is_beta() -> None:
    bad = readiness(certificate=_cert("warn"))
    assert bad["level"] == 4 and bad["levels"][4]["state"] == "failed" and "alpha_after_beta" in bad["summary"]
    good = readiness(certificate=_cert("pass"))
    assert good["level"] == 5
    absent = _cert("pass")
    absent["checks"].pop()
    assert readiness(certificate=absent)["level"] == 5
