"""Signal-level rows for verify --legs: timing significance and placebo, with explicit not-assessed rows."""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.verify.legs import verify_legs
from monte_neo.verify.legs_signal import legs_signal_rows

N = 2500


def _pair(seed: int, real_edge: bool) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    lx = np.cumsum(rng.normal(0, 0.01, N))
    if real_edge:  # a stationary AR(1) spread around a common stochastic trend
        spread = np.zeros(N)
        for t in range(1, N):
            spread[t] = 0.85 * spread[t - 1] + rng.normal(0, 0.01)
        ly = lx + spread
        pos = -np.sign(np.r_[0.0, spread[:-1]])  # short the spread when it was high at the previous close
    else:  # independent walks, an arbitrary position
        ly = np.cumsum(rng.normal(0, 0.01, N))
        pos = np.where((np.arange(N) // 50) % 2 == 0, 1.0, -1.0)
    table = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=N, freq="h"), "px_y": np.exp(ly), "px_x": np.exp(lx), "qty_y": pos, "qty_x": -pos})
    pnl = table["qty_y"].to_numpy()[1:] * np.diff(ly) + table["qty_x"].to_numpy()[1:] * np.diff(lx)
    table["reported_return"] = np.r_[0.0, pnl]
    return table


def _rows(table: pd.DataFrame) -> dict[str, dict]:
    from monte_neo.verify.legs import load_legs

    return {r["id"]: r for r in legs_signal_rows(load_legs(table), n_shifts=200)}


def test_real_mean_reversion_passes_timing_and_placebo() -> None:
    rows = _rows(_pair(1, True))
    assert rows["legs_timing_significance"]["status"] == "pass"
    assert rows["legs_placebo"]["status"] == "pass"


def test_no_edge_does_not_pass_and_honest_pair_is_not_rejected() -> None:
    table = _pair(2, False)
    rows = _rows(table)
    assert rows["legs_timing_significance"]["status"] in ("warn", "skip")
    rep = verify_legs(table, periods_per_year=8760)
    assert next(c for c in rep["checks"] if c["id"] == "accounting_mismatch")["status"] == "pass"


def test_drift_exposure_is_flagged_as_not_timing() -> None:
    """Always long one rising leg: profit from drift, so shifted copies earn the same."""
    rng = np.random.default_rng(3)
    ly = np.cumsum(rng.normal(0.004, 0.003, N))
    lx = np.cumsum(rng.normal(0, 0.01, N))
    table = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=N, freq="h"), "px_y": np.exp(ly), "px_x": np.exp(lx),
                          "qty_y": np.ones(N), "qty_x": np.zeros(N)})
    table["reported_return"] = np.r_[0.0, np.diff(ly)]
    rows = _rows(table)
    assert rows["legs_timing_significance"]["status"] == "warn" and "exposure" in rows["legs_timing_significance"]["summary"]


def test_boundaries_not_assessed_with_reasons() -> None:
    table = _pair(4, True)
    short = _rows(table.iloc[:40].reset_index(drop=True))
    assert short["legs_timing_significance"]["status"] == "skip" and "too few bars" in short["legs_timing_significance"]["summary"]
    flat = table.copy()
    flat["qty_y"] = 0.0
    flat["qty_x"] = 0.0
    flat_rows = _rows(flat)
    assert "never held" in flat_rows["legs_placebo"]["summary"]
    single = table.drop(columns=["px_x", "qty_x"])
    one = _rows(single)
    assert one["legs_placebo"]["status"] == "skip" and "two or more legs" in one["legs_placebo"]["summary"]
    for r in (short, flat_rows, one):
        assert r["legs_lookahead"]["status"] == "skip" and "not assessed" in r["legs_signal_ic"]["summary"]


def test_losing_legs_skip_and_cost_column_is_used() -> None:
    table = _pair(5, True)
    losing = table.copy()
    losing["qty_y"], losing["qty_x"] = -table["qty_y"], -table["qty_x"]
    assert _rows(losing)["legs_timing_significance"]["status"] == "skip"
    costly = table.copy()
    costly["cost"] = 0.0004
    assert _rows(costly)["legs_timing_significance"]["details"]["actual_return"] < _rows(table)["legs_timing_significance"]["details"]["actual_return"]


def test_certificate_carries_rows_and_actions() -> None:
    rep = verify_legs(_pair(2, False), periods_per_year=8760)
    ids = {c["id"] for c in rep["checks"]}
    assert {"legs_timing_significance", "legs_placebo", "legs_lookahead", "legs_signal_ic"} <= ids
