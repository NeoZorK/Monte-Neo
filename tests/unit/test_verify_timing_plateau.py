"""Timing significance (circular shifts) and the grid parameter plateau."""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.backtest import ExecutionModel
from monte_neo.verify import checks as rows
from monte_neo.verify import verify_strategy
from monte_neo.verify.grid import plateau, plateau_row
from monte_neo.verify.timing import timing_significance


def _market(drift: float, phi: float = 0.0, n: int = 4000, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    eps = rng.normal(drift, 0.005, n)
    rets = np.zeros(n)
    for i in range(1, n):
        rets[i] = phi * rets[i - 1] + eps[i]
    close = 100.0 * np.exp(np.cumsum(rets))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=n, freq="h"),
            "open": open_, "high": np.maximum(open_, close) * 1.001,
            "low": np.minimum(open_, close) * 0.999, "close": close,
        }
    )


def _ohlc(df: pd.DataFrame) -> dict[str, np.ndarray]:
    return {k: df[k].to_numpy() for k in ("open", "high", "low", "close")}


CHEAP = ExecutionModel(side_mode="long_short", commission_bps=1.0, slippage_bps=1.0, warmup_bars=60)


def test_real_timing_beats_its_shifted_copies() -> None:
    df = _market(0.0, phi=0.2)
    sig = np.sign(df["close"].diff()).fillna(0).to_numpy().astype(np.int64)
    res = timing_significance(_ohlc(df), sig, CHEAP)
    assert res["status"] == "pass" and res["p_value"] <= 0.05 and res["share_beaten"] > 0.95


def test_drift_without_timing_is_a_warning() -> None:
    df = _market(0.0008)
    rng = np.random.default_rng(1)
    sig = np.repeat(rng.integers(0, 2, len(df) // 20 + 1), 20)[: len(df)]
    res = timing_significance(_ohlc(df), sig, CHEAP)
    assert res["actual_return"] > 0 and res["status"] == "warn"
    report = verify_strategy(df, signals=sig, model=CHEAP)
    row = next(c for c in report["checks"] if c["id"] == "timing_significance")
    assert row["status"] == "warn" and report["metrics"]["timing_p_value"] == res["p_value"]
    assert any(a.startswith("The profit comes from market exposure") for a in report["next_actions"])


def test_timing_skips() -> None:
    short = _market(0.0, n=15)  # shifts must start 10 bars away and end 10 bars before the end
    assert timing_significance(_ohlc(short), np.ones(15, dtype=np.int64), CHEAP)["status"] == "skip"
    big = _market(0.0, n=400)
    assert timing_significance(_ohlc(big), np.zeros(400, dtype=np.int64), CHEAP)["status"] == "skip"  # no positions
    assert rows.timing_row(None)["status"] == "skip"
    assert rows.timing_row({"status": "skip"})["summary"] == "timing: no positions or too few bars"


def test_plateau() -> None:
    grid = {"a": [1, 2, 3], "b": [[0], [1]]}  # list values must work too
    combos = [{"a": a, "b": b} for a in grid["a"] for b in grid["b"]]
    peak = np.array([0.0, 0.1, 1.0, 0.0, 0.1, 0.0])  # best = (a=2, b=[0]); neighbours are poor
    info = plateau(grid, combos, peak, 2)
    assert sorted(info["neighbour_sharpes"]) == [0.0, 0.0, 0.1]  # a=1, b=[1], a=3
    assert plateau_row(info)["status"] == "warn"
    flat = np.array([0.9, 0.9, 1.0, 0.95, 0.9, 0.9])
    assert plateau_row(plateau(grid, combos, flat, 2))["status"] == "pass"
    assert plateau_row(plateau({"a": [1]}, [{"a": 1}], np.array([0.5]), 0))["summary"].endswith("no neighbouring combos")
    assert plateau_row(plateau(grid, combos, -flat, 2))["summary"].endswith("best combo is not profitable")
