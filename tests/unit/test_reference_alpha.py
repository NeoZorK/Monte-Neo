"""Reference alpha 1 (trend_v1): causal, runs on all synthetic sets, honest verdicts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pandas as pd
import pytest

from monte_neo.disclaimer import FULL
from monte_neo.verify import verify_strategy

ROOT = Path(__file__).resolve().parents[2] / "examples" / "reference_alpha"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_ra_{name}", ROOT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


data = _load("make_data")
trend = _load("trend_v1")

N_SYM, YEARS = 12, 12  # the demo size: smaller sets are too noisy to say anything (see README)


@pytest.fixture(scope="module")
def sets() -> dict[str, pd.DataFrame]:
    return {
        "trends": data.trends(N_SYM, YEARS),
        "random": data.random_walks(N_SYM, YEARS),
        "choppy": data.choppy(N_SYM, YEARS),
    }


def _verify(df: pd.DataFrame) -> dict:
    return verify_strategy(df, signal_fn=trend.signal, source=(ROOT / "trend_v1.py").read_text(), n_trials=1, probe_checks=6)


def _check(report: dict, check_id: str) -> dict:
    return next(c for c in report["checks"] if c["id"] == check_id)


def _net_return(report: dict) -> float:
    return float(_check(report, "net_profitability")["summary"].split("return ")[1].split("%")[0]) / 100


def test_disclaimer_is_the_full_text() -> None:
    assert trend.DISCLAIMER == FULL
    assert FULL[:40] in (trend.__doc__ or "")


def test_signal_shape_and_bounds(sets: dict[str, pd.DataFrame]) -> None:
    for df in sets.values():
        w = trend.signal(df)
        assert w.shape == (len(df),)
        assert np.isfinite(w).all()
        assert np.abs(w).max() <= trend.CAP_GROSS_PER_SYMBOL / N_SYM + 1e-12
        assert (w[: 200 * N_SYM] == 0).all()  # warm-up of about a year


def test_signal_is_causal_by_truncation(sets: dict[str, pd.DataFrame]) -> None:
    df = sets["trends"]
    full = trend.signal(df)
    stamps = sorted(df["timestamp"].unique())
    for cut in (stamps[400], stamps[900], stamps[1200]):
        head = df[df["timestamp"] <= cut]
        got = trend.signal(head)
        assert np.array_equal(got, full[: len(head)])


def test_trends_earn_after_costs(sets: dict[str, pd.DataFrame]) -> None:
    report = _verify(sets["trends"])
    assert _net_return(report) > 0
    for check_id in ("lookahead_truncation", "lookahead_perturbation", "lookahead_static_lint"):
        assert _check(report, check_id)["status"] == "pass"
    assert report["verdict"] != "REJECT"


def test_random_walks_show_no_significant_edge(sets: dict[str, pd.DataFrame]) -> None:
    report = _verify(sets["random"])
    dsr = float(_check(report, "deflated_sharpe")["summary"].split("Sharpe ")[1].split()[0])
    assert report["verdict"] != "PASS"
    assert dsr < 0.95


def test_choppy_market_does_not_pay(sets: dict[str, pd.DataFrame]) -> None:
    report = _verify(sets["choppy"])
    assert _net_return(report) <= 0.05
    assert report["verdict"] != "PASS"
