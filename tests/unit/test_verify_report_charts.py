"""The report's data blocks, charts and new page sections (headline, categories, evidence, trades)."""

from __future__ import annotations

import copy
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "traps"))
from trap_data import planted_momentum_ohlcv, universe_ohlcv  # noqa: E402

from monte_neo.backtest import synthetic_ohlcv  # noqa: E402
from monte_neo.backtest.model import ExecutionModel  # noqa: E402
from monte_neo.verify import model_from_costs, verify_grid, verify_strategy  # noqa: E402
from monte_neo.verify import report_charts as charts  # noqa: E402
from monte_neo.verify import report_data as data  # noqa: E402
from monte_neo.verify.report_html import render_html  # noqa: E402

TRAPS = Path(__file__).parents[1] / "traps" / "strategies"


@pytest.fixture(scope="module")
def honest() -> dict:
    df = planted_momentum_ohlcv()
    model = model_from_costs(commission_bps=1.0, slippage_bps=1.0, n_bars=len(df))
    return json.loads(json.dumps(verify_strategy(df, strategy=TRAPS / "momentum.py", model=model)))


@pytest.fixture(scope="module")
def leak() -> dict:
    return json.loads(json.dumps(verify_strategy(synthetic_ohlcv(1500, seed=13), strategy=TRAPS / "lookahead_shift.py")))


@pytest.fixture(scope="module")
def grid_report() -> dict:
    df = planted_momentum_ohlcv()
    model = model_from_costs(commission_bps=1.0, slippage_bps=1.0, n_bars=len(df))
    return json.loads(json.dumps(verify_grid(df, {"lookback": [1, 2, 3, 5]}, strategy=TRAPS / "momentum_params.py", model=model)))


def test_charts_block_is_small_and_complete(honest: dict) -> None:
    block = honest["charts"]
    assert set(block) == {"monthly", "returns_hist", "rolling_sharpe", "cost_curve", "timing", "trade_stats"}
    assert len(json.dumps(block)) < 12_000
    assert len(block["timing"]["shifted"]) == 200
    assert all(len(row) == 3 for row in block["monthly"])
    assert block["cost_curve"]["points"][0]["bps"] == 0.0


def test_charts_are_not_part_of_the_certificate_id() -> None:
    df = synthetic_ohlcv(800, seed=2)
    sig = (df["close"] > df["close"].rolling(20).mean()).astype(int).to_numpy()
    a = verify_strategy(df, signals=sig)
    b = json.loads(json.dumps(a))
    b["charts"] = {}
    assert a["certificate_id"] == b["certificate_id"] and "charts" in a


def test_monthly_returns() -> None:
    times = pd.Series(pd.date_range("2021-01-01", periods=400, freq="D"))
    equity = np.linspace(1.0, 2.0, 400)
    rows = data.monthly_returns(equity, times, 10)
    assert rows[0][:2] == [2021, 1] and rows[-1][:2] == [2022, 2]
    total = np.prod([1 + r[2] for r in rows])
    assert total == pytest.approx(equity[-1] / equity[10], rel=1e-3)
    assert data.monthly_returns(equity, None, 10) == []
    assert data.monthly_returns(equity[:30], times[:30], 0) == []  # under two months
    assert data.monthly_returns(np.array([1.0, 1.0]), times[:2], 1) == []


def test_returns_histogram() -> None:
    rng = np.random.default_rng(0)
    r = np.concatenate([rng.normal(0.001, 0.01, 500), np.zeros(300), [np.nan, 5.0, -5.0]])
    hist = data.returns_histogram(r)
    assert hist["n"] == 502 and len(hist["counts"]) == 30 and sum(hist["counts"]) == 502
    assert hist["edges"][0] < hist["mean"] < hist["edges"][-1]
    assert data.returns_histogram(np.zeros(100)) == {}
    assert data.returns_histogram(np.array([0.1, 0.2])) == {}
    assert data.returns_histogram(np.full(50, 0.01)) == {}  # no spread


def test_returns_histogram_degenerate_percentiles(monkeypatch: pytest.MonkeyPatch) -> None:
    r = np.array([0.0, 1.0] * 20)[1::2].copy() + np.arange(20) * 0.0  # a single distinct value after the filter
    assert data.returns_histogram(r) == {}
    monkeypatch.setattr(np, "percentile", lambda *a, **k: (0.5, 0.5))
    assert data.returns_histogram(np.linspace(0.1, 0.9, 50)) == {}


def test_rolling_sharpe() -> None:
    rng = np.random.default_rng(1)
    r = rng.normal(0.001, 0.01, 2000)
    block = data.rolling_sharpe(r, 252.0)
    assert block["window"] == 200 and len(block["values"]) == 100
    assert 0.0 < np.mean(block["values"]) < 10.0
    assert data.rolling_sharpe(r[:20], 252.0) == {}
    flat = data.rolling_sharpe(np.zeros(500), 252.0)
    assert set(flat["values"]) == {0.0}


def test_cost_curve_is_monotone_for_a_trend_follower() -> None:
    df = planted_momentum_ohlcv(n=2000)
    ohlc = {k: df[k].to_numpy() for k in ("open", "high", "low", "close")}
    r = df["close"].pct_change().fillna(0).to_numpy()
    model = ExecutionModel(commission_bps=1.0, slippage_bps=1.0, side_mode="long_short", warmup_bars=20)
    curve = data.cost_curve(ohlc, np.sign(r).astype(np.int64), model)
    returns = [p["return"] for p in curve["points"]]
    assert returns == sorted(returns, reverse=True) and curve["modeled_bps"] == 2.0


def test_trade_stats() -> None:
    trades = [
        {"pnl": 10.0, "qty": 1.0, "entry_px": 100.0, "entry_idx": 0, "exit_idx": 3},
        {"pnl": -5.0, "qty": 1.0, "entry_px": 100.0, "entry_idx": 4, "exit_idx": 6},
        {"pnl": -5.0, "qty": -1.0, "entry_px": 100.0, "entry_idx": 7, "exit_idx": 8},
        {"pnl": 20.0, "qty": 2.0, "entry_px": 50.0, "entry_idx": 9, "exit_idx": 19},
        {"pnl": 0.0, "qty": 0.0, "entry_px": 0.0, "entry_idx": 20, "exit_idx": 21},
    ]
    s = data.trade_stats(trades)
    assert s["n"] == 5 and s["win_rate"] == 0.4 and s["profit_factor"] == 3.0
    assert s["max_consecutive_wins"] == 1 and s["max_consecutive_losses"] == 2
    assert s["best"] == pytest.approx(0.2) and s["worst"] == pytest.approx(-0.05)
    assert s["avg_hold_bars"] == pytest.approx(3.4)
    assert data.trade_stats([]) == {}
    only_wins = data.trade_stats(trades[:1])
    assert only_wins["profit_factor"] is None and only_wins["avg_loss"] is None
    only_losses = data.trade_stats(trades[1:3])
    assert only_losses["avg_win"] is None


def test_weights_and_universes_have_no_trade_journal() -> None:
    df = planted_momentum_ohlcv(n=1500)
    weights = verify_strategy(df, signals=0.5 * np.sign(df["close"].pct_change().fillna(0).to_numpy()))
    assert "trade_stats" not in weights["charts"]
    uni = verify_strategy(universe_ohlcv(), strategy=TRAPS / "xs_equal_weight.py")
    assert "trade_stats" not in uni["charts"] and uni["charts"]["cost_curve"]


def test_very_active_strategies_skip_the_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    import monte_neo.verify.verdict as verdict

    monkeypatch.setattr(verdict, "MAX_TRADES_FOR_STATS", 10)
    df = synthetic_ohlcv(600, seed=3)
    report = verify_strategy(df, signals=np.where(np.arange(len(df)) % 2 == 0, 1, -1))
    assert "trade_stats" not in report["charts"]


def test_page_sections(honest: dict, leak: dict) -> None:
    page = render_html(honest)
    for text in ("Monthly returns", "Return distribution", "Rolling Sharpe", "Timing test", "Sensitivity to costs", "Trades", "win rate", "profit factor"):
        assert text in page
    assert page.count("<svg") == 7 and "@media print" in page
    assert re.search(r"class='card headline (good|warn)'", page)
    leak_page = render_html(leak)
    for text in ("Rejected:", "Evidence", "negative_shift", "cut after bar", "future rewritten after bar", "next-bar hit rate", "<code>"):
        assert text in leak_page
    assert "class='card headline bad'" in leak_page
    assert 'class="cat bad"' in leak_page and 'class="cat good"' in leak_page


def test_headline_variants() -> None:
    def head(verdict: str, statuses: list[tuple[str, str]]) -> str:
        checks = [{"id": f"c{i}", "category": "economics", "status": s, "summary": text} for i, (s, text) in enumerate(statuses)]
        return render_html({"verdict": verdict, "checks": checks})

    assert "Passed: no look-ahead found" in head("PASS", [("pass", "ok")])
    assert "Passed with warnings: slow." in head("PASS_WITH_WARNINGS", [("warn", "slow")])
    assert "Needs more evidence: a; b (and 1 more)." in head("NEEDS_MORE_EVIDENCE", [("warn", "a"), ("warn", "b"), ("warn", "c")])
    assert "Rejected: bad." in head("REJECT", [("fail", "bad"), ("pass", "fine")])
    assert "weird." in head("weird", [])  # unknown verdict, nothing to explain


def test_evidence_for_external_data_and_data_quality() -> None:
    checks = [
        {"id": "external_data", "category": "lookahead", "status": "fail", "summary": "x", "details": {"files": ["/data/prices.csv"], "connections": ["example.com"]}},
        {"id": "data_quality", "category": "integrity", "status": "warn", "summary": "y",
         "details": {"spike_examples": [{"bar": 7, "symbol": "AAA"}, "junk"], "split_examples": [{"bar": 9}]}},
        {"id": "lookahead_static_lint", "category": "lookahead", "status": "pass", "summary": "clean"},
        {"id": "determinism", "category": "integrity", "status": "fail", "summary": "z", "details": "not a dict"},
    ]
    page = render_html({"verdict": "REJECT", "checks": checks})
    for text in ("read /data/prices.csv", "connected to example.com", "spike at bar 7 (AAA)", "split-like jump at bar 9"):
        assert text in page


def test_grid_heat_map(grid_report: dict) -> None:
    assert len(grid_report["grid"]["combo_sharpes"]) == 4
    page = render_html(grid_report)
    assert "Sharpe per bar: rows lookback" in page and page.count("<svg") == 8


def test_grid_heat_map_two_parameters_and_hidden_ones() -> None:
    spec = {"a": [1, 2], "b": [10, 20, 30], "c": [0, 1]}
    sharpes = [round(0.01 * i - 0.03, 3) for i in range(12)]
    svg = charts.grid_heatmap({"spec": spec, "combo_sharpes": sharpes})
    assert svg.count("<rect") == 6 and "columns b" in svg and "0.080" in svg  # the best of each (a, b) cell
    assert charts.grid_heatmap({"spec": spec, "combo_sharpes": sharpes[:5]}) == ""  # size does not match the grid
    assert charts.grid_heatmap({"spec": {}, "combo_sharpes": [0.1]}) == ""
    assert charts.grid_heatmap({"spec": {"a": "not a list"}, "combo_sharpes": [0.1]}) == ""
    assert charts.grid_heatmap({}) == ""


def test_charts_survive_hostile_and_broken_input() -> None:
    junk = [None, "x", float("nan"), math.inf, True, [], {}, [1, "a", None], {"points": "no"}, -1, 10**400 if False else 1e308]
    for value in junk:
        for name in ("equity_chart", "rolling_sharpe_chart", "returns_histogram_chart", "timing_chart", "cost_chart", "grid_heatmap"):
            fn = getattr(charts, name)
            for wrapped in (value, {"equity": value, "benchmark": value, "values": value, "edges": value, "counts": value,
                                    "shifted": value, "actual": value, "points": value, "spec": value, "combo_sharpes": value}):
                assert isinstance(fn(wrapped if isinstance(wrapped, dict) else {"x": wrapped}), str)
        assert isinstance(charts.monthly_heatmap(value), str)


def test_equity_chart_variants() -> None:
    linear = charts.equity_chart({"equity": [1.0, 0.5, -0.2], "benchmark": [1.0, 1.1, 1.2], "bar": [0, 1, 2]})
    assert "log scale" not in linear and "bar 0" in linear
    log = charts.equity_chart({"equity": [1.0, 2.0, 3.0], "benchmark": [1.0, 1.0, 1.0], "time": ["2020-01-01T00:00", "2020-01-02", "2020-01-03"]})
    assert "log scale" in log and "2020-01-03" in log
    assert "No equity series" in charts.equity_chart({"equity": [1.0]})
    no_axes = charts.equity_chart({"equity": [1.0, 2.0], "benchmark": [], "time": "x", "bar": "y"})
    assert "bar 0" in no_axes and "bar 1" in no_axes


def test_monthly_heatmap_ignores_bad_rows() -> None:
    rows = [[2020, 1, 0.05], [2020, 13, 0.1], [99, 1, 0.1], [2020, 2, "x"], "junk", [2020, 3, -0.02], [2021, 1, 0.0]]
    svg = charts.monthly_heatmap(rows)
    assert svg.count("<rect") == 3 and "+5.0%" in svg and "-2.0%" in svg
    assert charts.monthly_heatmap([]) == "" and charts.monthly_heatmap(None) == ""


def test_histogram_marks_use_the_right_side_and_tone() -> None:
    hist = {"edges": [i / 10 for i in range(-5, 6)], "counts": [1, 3, 5, 3, 1, 1, 3, 5, 3, 1], "mean": -0.4}
    left = charts.returns_histogram_chart(hist)
    assert left.count('text-anchor="end"') == 1 and 'stroke="var(--bad)"' in left  # only the axis label
    hist["mean"] = 0.45
    right = charts.returns_histogram_chart(hist)
    assert right.count('text-anchor="end"') == 2 and 'stroke="var(--good)"' in right
    assert charts.returns_histogram_chart({"edges": [0, 1], "counts": [1, 2, 3]}) == ""


def test_timing_and_cost_chart_details() -> None:
    shifted = [-0.05 + 0.001 * i for i in range(100)]
    assert "actual +30.0% (p 0.010)" in charts.timing_chart({"shifted": shifted, "actual": 0.3, "p_value": 0.01})
    assert "actual +30.0%" in charts.timing_chart({"shifted": shifted, "actual": 0.3, "p_value": None})
    assert charts.timing_chart({"shifted": [0.1] * 20, "actual": 0.1}) == ""  # no spread
    points = [{"bps": b, "return": 1 - b / 10} for b in (0, 5, 10, 20)] + [{"bps": "x"}, "junk"]
    svg = charts.cost_chart({"points": points, "modeled_bps": 7})
    assert "modeled 7 bps" in svg and charts.cost_chart({"points": points, "modeled_bps": 500}).count("modeled") == 0
    assert charts.cost_chart({"points": points[:1]}) == ""


def test_rolling_sharpe_chart_needs_points() -> None:
    assert charts.rolling_sharpe_chart({"values": [1.0]}) == ""
    assert "polyline" in charts.rolling_sharpe_chart({"values": [1.0, -2.0, 3.0]})


def test_page_with_hostile_charts_block_is_still_escaped_and_scriptless(honest: dict) -> None:
    evil = copy.deepcopy(honest)
    evil["charts"] = {"monthly": [["<script>", 1, 1]], "returns_hist": "x", "rolling_sharpe": [], "cost_curve": {"points": ["<img src=x onerror=1>"]},
                      "timing": {"shifted": ["<b>"], "actual": "<i>"}, "trade_stats": {"n": "<script>alert(1)</script>", "win_rate": "1"}}
    evil["grid"] = {"spec": {"<b>x</b>": [1, 2]}, "combo_sharpes": [0.1, 0.2], "n_combos": "<u>", "walk_forward": {}, "plateau": {"median_ratio": "1"}}
    page = render_html(evil)
    assert "<script" not in page.lower() and "<img" not in page and "<b>x" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_cli_and_mcp_write_the_same_page(tmp_path: Path, honest: dict) -> None:
    cert = tmp_path / "cert.json"
    cert.write_text(json.dumps(honest), encoding="utf-8")
    from monte_neo.mcp.tools import render_report

    out = render_report(str(cert), str(tmp_path / "r.html"))
    assert out["bytes"] > 20_000
    assert (tmp_path / "r.html").read_text(encoding="utf-8") == render_html(honest)


def test_gallery_reports_are_static_and_linked() -> None:
    root = Path(__file__).parents[2]
    pages = sorted((root / "docs" / "assets" / "reports").glob("*.html"))
    gallery = (root / "docs" / "gallery.md").read_text(encoding="utf-8")
    assert {p.stem for p in pages} == {"leak", "no-edge", "honest", "grid", "universe", "bad-ticks"}
    for path in pages:
        page = path.read_text(encoding="utf-8")
        assert "<script" not in page.lower() and "Content-Security-Policy" in page
        assert f"assets/reports/{path.name}" in gallery
        assert ("Evidence" in page) == (path.stem in {"leak", "bad-ticks"})  # only leaks and bad data have evidence
