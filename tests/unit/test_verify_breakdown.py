"""Buy-and-hold benchmark, period and regime breakdown, chart series."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import ExecutionModel, synthetic_ohlcv
from monte_neo.verify import checks as rows
from monte_neo.verify import verify_strategy
from monte_neo.verify.breakdown import _period_bounds, periods, regimes, series


def _daily(n: int, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, n)))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    return pd.DataFrame(
        {
            "timestamp": pd.bdate_range("2018-01-01", periods=n),
            "open": open_, "high": np.maximum(open_, close) * 1.002,
            "low": np.minimum(open_, close) * 0.998, "close": close,
        }
    )


@pytest.mark.parametrize(
    ("days", "freq", "first"),
    [(1200, "year", "2018"), (300, "quarter", "2018-Q1"), (90, "month", "2018-01"), (30, "segment", "bars 0-6")],
)
def test_period_frequency(days: int, freq: str, first: str) -> None:
    times = pd.DatetimeIndex(pd.date_range("2018-01-01", periods=days, freq="D", tz="UTC"))
    got, bounds = _period_bounds(times, 0, days)
    assert got == freq and bounds[0][0] == first
    assert bounds[0][1] == 0 and bounds[-1][2] == days - 1
    assert all(b[1] == a[2] + 1 for a, b in zip(bounds[:-1], bounds[1:], strict=True))  # contiguous


def test_periods_chain_to_the_total_and_segments_without_time() -> None:
    df = _daily(900)  # over three years after warm-up: yearly periods
    report = verify_strategy(df, signals=np.sign(df["close"].diff(5).fillna(0)).to_numpy(), min_trades=1)
    by_period = report["breakdown"]["periods"]
    chained = np.prod([1 + p["return"] for p in by_period]) - 1
    assert chained == pytest.approx(report["metrics"]["total_return"], abs=1e-9)
    assert report["breakdown"]["frequency"] == "year"
    no_time = periods(np.linspace(1, 2, 100), np.ones(100), np.ones(100), None, 10, 252.0)
    assert no_time["frequency"] == "segment" and len(no_time["periods"]) == 4
    bad_time = periods(np.linspace(1, 2, 5), np.ones(5), np.ones((5, 2)), ["x"] * 5, 0, 252.0)
    assert bad_time["frequency"] == "segment"
    zero = periods(np.zeros(8), np.zeros(8), np.zeros(8), None, 0, 252.0)
    assert all(p["return"] == 0.0 and p["benchmark_return"] == 0.0 for p in zero["periods"])


def test_period_consistency() -> None:
    table = {"periods": [{"period": p, "return": r} for p, r in (("A", 0.5), ("B", -0.1), ("C", -0.2))]}
    warn = rows.period_row(table, 0.08)
    assert warn["status"] == "warn" and "(A)" in warn["summary"]
    good = {"periods": [{"period": p, "return": r} for p, r in (("A", 0.1), ("B", 0.05), ("C", -0.01))]}
    assert rows.period_row(good, 0.14)["summary"] == "profitable in 2 of 3 periods"
    assert rows.period_row(good, -0.1)["status"] == "skip"
    assert rows.period_row({"periods": good["periods"][:2]}, 0.1)["summary"] == "fewer than 3 periods"


def test_benchmark_in_the_report() -> None:
    df = synthetic_ohlcv(1500, seed=9)
    sig = (df["close"] > df["close"].rolling(30).mean()).astype(int).to_numpy()
    report = verify_strategy(df, signals=sig)
    bench = next(c for c in report["checks"] if c["id"] == "benchmark")
    assert bench["status"] == "info" and bench["summary"].startswith("buy & hold")
    assert bench["details"]["excess_return"] == pytest.approx(
        report["metrics"]["total_return"] - report["metrics"]["benchmark_total_return"]
    )
    assert report["benchmark"]["total_return"] == report["metrics"]["benchmark_total_return"]
    s = report["series"]
    assert len(s["equity"]) == len(s["benchmark"]) == len(s["bar"]) <= 400 and s["equity"][0] == 1.0
    assert s["time"] is not None and s["time"][0].startswith("2024")


def test_regimes() -> None:
    equity = np.linspace(100, 150, 400)
    market = 100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.01, 400)))
    out = regimes(equity, market, 10, 252.0)
    reg = out["regimes"]
    assert reg["rising"]["bars"] + reg["falling"]["bars"] == reg["calm"]["bars"] + reg["volatile"]["bars"]
    assert reg["rising"]["share"] + reg["falling"]["share"] == pytest.approx(1.0)
    assert regimes(np.ones(15), np.ones(15), 0, 252.0)["regimes"] == {}


def test_series_without_time() -> None:
    s = series(np.linspace(100, 200, 50), np.zeros(50), None, 5)
    assert s["time"] is None and s["equity"][0] == 1.0 and s["benchmark"][0] == 0.0
    assert s["bar"][0] == 5 and s["bar"][-1] == 49


def test_benchmark_uses_the_same_costs() -> None:
    df = _daily(300)
    free = verify_strategy(df, signals=np.ones(300), model=ExecutionModel(side_mode="long_short", commission_bps=0, slippage_bps=0, warmup_bars=10))
    paid = verify_strategy(df, signals=np.ones(300), model=ExecutionModel(side_mode="long_short", commission_bps=50, slippage_bps=0, warmup_bars=10))
    assert free["metrics"]["benchmark_total_return"] > paid["metrics"]["benchmark_total_return"]
    assert paid["metrics"]["total_return"] == pytest.approx(paid["metrics"]["benchmark_total_return"])
