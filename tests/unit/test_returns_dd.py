"""Allocator due diligence on a bare return series."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.verify.returns_dd import demo_returns, load_returns, recheck_returns, verify_returns
from monte_neo.verify.schema import DISCLAIMER, VERDICT_JSON_SCHEMA, VERDICTS


def _status(report: dict, check_id: str) -> str:
    return next(c["status"] for c in report["checks"] if c["id"] == check_id)


@pytest.fixture(scope="module")
def series() -> dict[str, pd.Series]:
    return demo_returns(0)


def test_honest_series_has_no_fail(series: dict[str, pd.Series]) -> None:
    rep = verify_returns(series["honest"])
    assert not [c for c in rep["checks"] if c["status"] == "fail"]
    assert _status(rep, "return_smoothing") == "pass"
    assert _status(rep, "returns_only_scope") == "info"
    assert rep["scope"].startswith("Return series only")
    assert rep["disclaimer"] == DISCLAIMER


def test_smoothed_series_warns(series: dict[str, pd.Series]) -> None:
    rep = verify_returns(series["smoothed"])
    assert _status(rep, "return_smoothing") == "warn"
    row = next(c for c in rep["checks"] if c["id"] == "return_smoothing")
    assert row["details"]["unsmoothed_sharpe"] < row["details"]["sharpe"]


def test_too_good_series_fails(series: dict[str, pd.Series]) -> None:
    rep = verify_returns(series["too_good"])
    assert _status(rep, "implausible_consistency") == "fail"
    assert _status(rep, "zero_kink") == "warn"
    assert rep["verdict"] == "NEEDS_MORE_EVIDENCE"


def test_drawdown_too_shallow_warns() -> None:
    rng = np.random.default_rng(3)
    r = rng.normal(0.01, 0.03, 120)
    r = np.where(r < 0, r * 0.1, r)  # losses squeezed: drawdown far below the iid expectation
    rep = verify_returns(pd.Series(r, pd.date_range("2015-01-31", periods=120, freq="ME")))
    assert _status(rep, "drawdown_consistency") == "warn"


def test_report_shape_and_schema(series: dict[str, pd.Series]) -> None:
    rep = verify_returns(series["honest"], benchmark=series["smoothed"], n_strategies=3, claim={"sharpe": 0.5})
    for key in VERDICT_JSON_SCHEMA["required"]:
        assert key in rep
    assert rep["schema"] == "strategy-verdict/1" and rep["verdict"] in VERDICTS
    for c in rep["checks"]:
        assert {"id", "category", "status", "summary"} <= set(c)
    assert _status(rep, "benchmark_relation") == "info"
    assert rep["reproducibility"]["n_trials"] == 3
    assert rep["reproducibility"]["settings"]["kind"] == "returns"
    assert {"n", "sharpe", "unsmoothed_sharpe", "max_drawdown", "psr", "dsr"} <= set(rep["metrics"])


def test_claim_overstated_fails(series: dict[str, pd.Series]) -> None:
    rep = verify_returns(series["honest"], claim={"sharpe": 3.0, "max_drawdown": 0.02})
    assert _status(rep, "claim_consistency") == "fail"
    ok = verify_returns(series["honest"], claim={"sharpe": 0.1})
    assert _status(ok, "claim_consistency") == "pass"


def test_deflation_with_many_strategies(series: dict[str, pd.Series]) -> None:
    one = verify_returns(series["honest"])["metrics"]["dsr"]
    many = verify_returns(series["honest"], n_strategies=500)["metrics"]["dsr"]
    assert many < one


def test_recheck_reproduces(series: dict[str, pd.Series]) -> None:
    rep = verify_returns(series["honest"], n_strategies=2, seed=5)
    assert recheck_returns(rep, series["honest"])["reproduced"] is True
    other = recheck_returns(rep, series["smoothed"])
    assert other["reproduced"] is False and other["data_matches"] is False


def test_percent_detection(series: dict[str, pd.Series]) -> None:
    honest = series["honest"]
    df = pd.DataFrame({"date": honest.index, "ret": honest.to_numpy() * 100.0})
    assert np.allclose(load_returns(df, "ret").to_numpy(), honest.to_numpy())
    assert np.allclose(load_returns(df, "ret", percent=True).to_numpy(), honest.to_numpy())
    dec = pd.DataFrame({"date": honest.index, "ret": honest.to_numpy()})
    assert np.allclose(load_returns(dec).to_numpy(), honest.to_numpy())


def test_load_from_csv(tmp_path, series: dict[str, pd.Series]) -> None:
    path = tmp_path / "r.csv"
    series["honest"].rename("fund").rename_axis("date").to_csv(path)
    assert load_returns(path).size == 120


def test_load_errors(series: dict[str, pd.Series]) -> None:
    honest = series["honest"]
    with pytest.raises(ValueError, match="no date column"):
        load_returns(pd.DataFrame({"ret": honest.to_numpy()}))
    dup = pd.DataFrame({"date": list(honest.index[:-1]) + [honest.index[0]], "ret": honest.to_numpy()})
    with pytest.raises(ValueError, match="duplicate"):
        load_returns(dup)
    with pytest.raises(ValueError, match="at least 24"):
        load_returns(honest.iloc[:12])
    with pytest.raises(ValueError, match="not found"):
        load_returns(pd.DataFrame({"date": honest.index, "ret": honest.to_numpy()}), "nope")


def test_round_numbers_flags_rounded_data() -> None:
    rng = np.random.default_rng(1)
    r = np.round(rng.normal(0.007, 0.03, 120) / 0.0005) * 0.0005 + rng.normal(0, 1e-7, 120) * (rng.random(120) < 0.3)
    idx = pd.date_range("2015-01-31", periods=120, freq="ME")
    rep = verify_returns(pd.Series(r, idx))
    assert _status(rep, "round_numbers") == "warn"
    assert _status(verify_returns(demo_returns(0)["honest"].round(3)), "round_numbers") == "skip"
