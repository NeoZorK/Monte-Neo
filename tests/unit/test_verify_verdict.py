"""Unit tests for verdict aggregation, check rows and verify_strategy."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import ExecutionModel, export_signals, synthetic_ohlcv
from monte_neo.verify import (
    VERDICT_JSON_SCHEMA,
    VERDICT_SCHEMA_ID,
    aggregate_verdict,
    model_from_costs,
    to_jsonable,
    verify_strategy,
)
from monte_neo.verify import checks as rows


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return synthetic_ohlcv(1500, seed=5)


def _row(status: str, category: str = "statistics") -> dict:
    return rows.check("x", category, status, "s")


def test_aggregate_verdict() -> None:
    assert aggregate_verdict([_row("pass"), _row("info"), _row("skip")]) == "PASS"
    assert aggregate_verdict([_row("pass"), _row("warn")]) == "PASS_WITH_WARNINGS"
    assert aggregate_verdict([_row("fail"), _row("warn")]) == "NEEDS_MORE_EVIDENCE"
    assert aggregate_verdict([_row("fail"), _row("fail", "lookahead")]) == "REJECT"


def test_to_jsonable() -> None:
    out = to_jsonable({"a": np.int64(1), "b": np.float32(0.5), "c": np.bool_(True), "d": (np.nan, 1.0), "e": np.arange(2), 3: "k"})
    assert out == {"a": 1, "b": 0.5, "c": True, "d": [None, 1.0], "e": [0, 1], "3": "k"}
    json.dumps(out, allow_nan=False)


def test_check_rows() -> None:
    ohlc = {"open": np.array([1.0, np.nan]), "high": np.array([0.5, 2.0]), "low": np.array([1.0, 1.0]), "close": np.array([-1.0, 1.0])}
    bad = rows.data_integrity(ohlc)
    assert bad["status"] == "fail" and bad["details"]["inverted_bars"] == 1
    assert rows.probe_row("lookahead_truncation", None, "t")["status"] == "skip"
    assert rows.probe_row("determinism", {"status": "fail"}, "d")["summary"] == "signal() is not deterministic"
    assert "LEAK" in rows.probe_row("lookahead_truncation", {"status": "fail"}, "t")["summary"]
    assert rows.lint_row(None)["status"] == "skip"
    assert rows.accuracy_row({"status": "skip", "hit_rate": None})["summary"].endswith("too few active bars")
    model0 = ExecutionModel(commission_bps=0.0, slippage_bps=0.0)
    econ = {r["id"]: r for r in rows.economics_rows(model0, 0.1, {"breakeven_bps": 0.5}, {"status": "pass"})}
    assert econ["costs_modeled"]["status"] == "warn"
    assert econ["cost_margin"]["status"] == "warn"
    econ = {r["id"]: r for r in rows.economics_rows(ExecutionModel(), -0.1, {"breakeven_bps": 0.0}, {"status": "warn"})}
    assert econ["net_profitability"]["status"] == "fail"
    assert econ["cost_margin"]["status"] == "skip"
    assert econ["delay_sensitivity"]["summary"].startswith("profit vanishes")
    dsr = {"deflated_sharpe": 0.7, "n_trials": 3}
    ho = {"train_sharpe": 0.1, "holdout_sharpe": -0.1}
    stats = {r["id"]: r for r in rows.statistics_rows(dsr, 5, 30, True, ho)}
    assert stats["deflated_sharpe"]["status"] == "warn"
    assert stats["trials_disclosed"]["status"] == "pass"
    assert stats["holdout_consistency"]["status"] == "warn"
    lint = rows.lint_row({"status": "fail", "findings": [{"rule": "negative_shift", "line": 4}]})
    actions = rows.next_actions([lint, _row("warn"), rows.check("sample_size", "statistics", "fail", "s")])
    assert actions[0].startswith("Fix the flagged") and actions[0].endswith("Lines: 4.")
    assert len(actions) == 2


def test_verify_requires_input(df) -> None:
    with pytest.raises(ValueError, match="provide signals"):
        verify_strategy(df)
    with pytest.raises(ValueError, match="warmup"):
        verify_strategy(df.iloc[:5], signals=np.ones(5), model=ExecutionModel(warmup_bars=10))


def test_verify_bad_data_short_circuits(df) -> None:
    broken = df.copy()
    broken.loc[10, "close"] = np.nan
    report = verify_strategy(broken, signals=np.ones(len(df)))
    assert report["verdict"] == "REJECT"
    assert [c["id"] for c in report["checks"]] == ["data_integrity"]
    assert report["metrics"] == {} and report["reproducibility"]["signals_sha256"] is None


def test_verify_signals_only(df) -> None:
    sig = (df["close"] > df["close"].rolling(30).mean()).astype(int)
    report = verify_strategy(df, signals=sig, n_trials=3, trial_sharpes=[0.0, 0.01, 0.02], periods_per_year=365)
    assert report["schema"] == VERDICT_SCHEMA_ID
    statuses = {c["id"]: c["status"] for c in report["checks"]}
    assert statuses["lookahead_truncation"] == "skip"
    assert statuses["lookahead_static_lint"] == "skip"
    assert statuses["trials_disclosed"] == "pass"
    assert set(VERDICT_JSON_SCHEMA["required"]) <= set(report)
    json.dumps(report, allow_nan=False)
    again = verify_strategy(df, signals=sig, n_trials=3, trial_sharpes=[0.0, 0.01, 0.02], periods_per_year=365)
    assert again["certificate_id"] == report["certificate_id"]


def test_verify_signal_fn_with_source(df) -> None:
    def fn(d: pd.DataFrame) -> pd.Series:
        return np.sign(d["close"].shift(-1) - d["close"])

    report = verify_strategy(df, signal_fn=fn, source="x = close.shift(-1)\n")
    assert report["verdict"] == "REJECT"
    assert report["reproducibility"]["source_sha256"]
    assert any("Lines: 1." in a for a in report["next_actions"])


def test_model_from_costs() -> None:
    m = model_from_costs(commission_bps=1, slippage_bps=2, side_mode="long_short", n_bars=100)
    assert (m.commission_bps, m.slippage_bps, m.side_mode, m.warmup_bars) == (1.0, 2.0, "long_short", 10)
    assert model_from_costs(warmup_bars=5).warmup_bars == 5
    assert model_from_costs().warmup_bars == 60


def test_export_signals(df) -> None:
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    sig = np.where(np.arange(len(df)) % 100 < 50, 2.0, -np.nan)
    out = export_signals(o, h, l, c, sig, model=ExecutionModel(warmup_bars=10), include_equity=True)
    assert out["engine"] == "monte_neo.backtest.export_signals"
    assert out["signal"]["exposure"] == pytest.approx(0.5)
    assert out["signal"]["position_changes"] > 0 and not out["signal"]["has_short"]
    assert len(out["signal"]["sha256"]) == 64 and "equity" in out
    with pytest.raises(ValueError, match="length"):
        export_signals(o, h, l, c, sig[:-1])
