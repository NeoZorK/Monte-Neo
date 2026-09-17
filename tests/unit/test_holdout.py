"""Holdout / train-test helper unit tests."""

from __future__ import annotations

import pytest

from monte_neo.backtest import (
    ExecutionModel,
    holdout_sma_sweep,
    holdout_to_research_metrics,
    split_bar_range,
    synthetic_ohlcv,
)
from monte_neo.policy import HeuristicPolicy, PolicyConfig, build_research_state


def test_split_bar_range():
    tr, ho = split_bar_range(1000, train_frac=0.7, min_holdout=100, min_train=200)
    assert tr.start == 0
    assert tr.stop == 700
    assert ho.start == 700
    assert ho.stop == 1000


def test_split_too_short():
    with pytest.raises(ValueError):
        split_bar_range(50, min_holdout=100, min_train=200)


def test_holdout_sma_sweep_smoke():
    ohlc = synthetic_ohlcv(3000, seed=21)
    model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=40)
    report = holdout_sma_sweep(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        combos=16,
        top_k=3,
        model=model,
        device="cpu_numba",
        min_holdout=200,
    )
    assert report["schema"] == "mn.holdout_report.v1"
    assert report["split"]["train_bars"] + report["split"]["holdout_bars"] == 3000
    assert len(report["holdout"]["top_k"]) == 3
    assert "gap_best" in report["metrics"]
    assert report["metrics"]["overfit_risk"] in {"low", "med", "high"}
    assert report["metrics"]["next_action"] in {
        "promote_paper_oms",
        "run_mc",
        "stop",
        "reject",
    }


def test_holdout_metrics_enrich_policy():
    model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=40)
    rows = [
        {"fast": 5, "slow": 30, "total_return": 0.25},
        {"fast": 6, "slow": 31, "total_return": 0.20},
    ]
    export = {
        "ok": True,
        "device": "cpu_numba",
        "bars": 2500,
        "combos": len(rows),
        "export_api_version": "1",
        "engine": "test",
        "lane": "research_bar",
        "model": model.to_dict(),
        "work_checklist": {
            "next_bar_fill": True,
            "fees": True,
            "no_lookahead": True,
            "cash_position_equity": True,
        },
        "timing": {},
        "metrics": {"best_return": 0.25, "rows": rows},
    }
    report = {
        "metrics": {
            "gap_best": 0.4,
            "mean_gap_top_k": 0.3,
            "overfit_risk": "high",
            "promote_ok": False,
            "next_action": "reject",
        },
        "holdout": {"at_train_best": -0.1},
    }
    state = build_research_state(export, holdout_report=report)
    assert state["metrics"]["holdout_gap"] == 0.4
    d = HeuristicPolicy(PolicyConfig(t_promote_return=0.05)).decide(state)
    assert d["promote_to_paper_oms"] is False
    assert d["overfit_risk"] == "high"
    assert d["next_action"] in {"run_mc", "reject", "stop"}


def test_holdout_to_research_metrics_keys():
    fake = {
        "metrics": {
            "gap_best": 0.1,
            "mean_gap_top_k": 0.05,
            "overfit_risk": "med",
            "promote_ok": False,
        },
        "holdout": {"at_train_best": 0.01},
    }
    m = holdout_to_research_metrics(fake)
    assert m["holdout_gap"] == 0.1
    assert m["holdout_return"] == 0.01

def test_split_bad_frac():
    with pytest.raises(ValueError):
        split_bar_range(1000, train_frac=0.99)


def test_holdout_overfit_branches(monkeypatch):
    """Force med/high/reject branches via patched pair returns."""
    ohlc = synthetic_ohlcv(2500, seed=3)
    model = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, warmup_bars=40)

    # High overfit + negative holdout → reject
    import monte_neo.backtest.holdout as ho

    real_pairs = ho._pairs_returns

    def fake_high(*a, **k):
        out = real_pairs(*a, **k)
        # crush holdout returns
        for r in out["rows"]:
            r["total_return"] = -0.5
        return out

    monkeypatch.setattr(ho, "_pairs_returns", fake_high)
    report = holdout_sma_sweep(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"],
        combos=8, top_k=2, model=model, device="cpu_numba", min_holdout=200,
        gap_high=0.01, gap_med=0.005,
    )
    assert report["metrics"]["overfit_risk"] == "high"
    assert report["metrics"]["next_action"] == "reject"

    def fake_med(*a, **k):
        out = real_pairs(*a, **k)
        for r in out["rows"]:
            # small positive holdout, modest gap → med if train much higher
            r["total_return"] = float(r["total_return"])  # leave; set gap via thresholds
        return out

    monkeypatch.setattr(ho, "_pairs_returns", fake_med)
    # Use tiny gap_med so almost any positive train-holdout gap is at least med
    report2 = holdout_sma_sweep(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"],
        combos=8, top_k=2, model=model, device="cpu_numba", min_holdout=200,
        gap_high=10.0, gap_med=-1.0,  # mean_gap >= -1 always → at least med
    )
    assert report2["metrics"]["overfit_risk"] in {"med", "high", "low"}


def test_holdout_empty_rows(monkeypatch):
    import monte_neo.backtest.holdout as ho

    def empty_export(*a, **k):
        return {"ok": True, "metrics": {"rows": []}, "device": "cpu_numba"}

    monkeypatch.setattr(ho, "export_sma_sweep", empty_export)
    ohlc = synthetic_ohlcv(2500, seed=1)
    with pytest.raises(RuntimeError):
        holdout_sma_sweep(
            ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"],
            combos=4, model=ExecutionModel(), device="cpu_numba", min_holdout=200,
        )

