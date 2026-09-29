"""Universes: a long table with a symbol column, weights per (timestamp, symbol)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import ExecutionModel
from monte_neo.backtest.weight_engine import run_weight_backtest
from monte_neo.cli.verify_cmd import main as cli_main
from monte_neo.mcp import tools
from monte_neo.verify import load_ohlcv, recheck_certificate, verify_grid, verify_strategy
from monte_neo.verify.market import UniverseMarket, bar_count, market_for

sys.path.insert(0, str(Path(__file__).parents[1] / "traps"))
from trap_data import universe_ohlcv  # noqa: E402

TRAPS = Path(__file__).parents[1] / "traps" / "strategies"


@pytest.fixture(scope="module")
def uni() -> pd.DataFrame:
    return universe_ohlcv()


def _statuses(report: dict) -> dict[str, str]:
    return {c["id"]: c["status"] for c in report["checks"]}


def _momentum(df: pd.DataFrame, lookback: int = 20) -> np.ndarray:
    past = df.groupby("symbol")["close"].pct_change(lookback)
    rank = past.groupby(df["timestamp"]).rank(pct=True)
    return np.where(rank > 0.7, 1.0, np.where(rank <= 0.3, -1.0, 0.0))


def test_market_layout(uni) -> None:
    m = market_for(load_ohlcv(uni.sample(frac=1.0, random_state=3)))
    assert isinstance(m, UniverseMarket) and m.symbols == [f"S{k}" for k in range(6)]
    assert m.n_bars == 700 and bar_count(uni) == 700 and bar_count(uni.drop(columns="symbol")) == len(uni)
    assert m.ohlc["close"].shape == (700, 6)
    assert np.isnan(m.ohlc["close"][0, 1]) and np.isnan(m.ohlc["close"][-1, 2])  # listed late, delisted
    assert (m.frame["timestamp"].diff().dropna() >= pd.Timedelta(0)).all()  # rows sorted by time
    bench = m.benchmark_positions()
    assert np.allclose(bench.sum(axis=1), 1.0) and bench[0, 1] == 0.0
    assert m.market_close()[0] == 1.0 and np.isfinite(m.market_close()).all()


def test_row_order_does_not_change_the_certificate(uni) -> None:
    a = verify_strategy(uni, signal_fn=_momentum)
    b = verify_strategy(uni.sample(frac=1.0, random_state=9), signal_fn=_momentum)
    assert a["certificate_id"] == b["certificate_id"]
    assert a["reproducibility"]["universe"] == {"symbols": 6, "bars": 700}
    assert a["metrics"]["symbols"] == 6 and a["metrics"]["rows"] == len(uni)
    assert 0.0 < a["metrics"]["mean_gross_exposure"] <= 1.0 + 1e-12


def test_honest_universe_strategy(uni) -> None:
    report = verify_strategy(uni, signal_fn=_momentum)
    statuses = _statuses(report)
    for check_id in ("lookahead_truncation", "lookahead_perturbation", "determinism", "survivorship"):
        assert statuses[check_id] == "pass", (check_id, report["reasons"])
    assert report["benchmark"]["description"].startswith("equal weight")


def test_aliases_and_input_errors(uni) -> None:
    renamed = load_ohlcv(uni.rename(columns={"symbol": "Ticker", "timestamp": "date"}))
    assert "symbol" in renamed.columns and "timestamp" in renamed.columns
    with pytest.raises(ValueError, match="needs a timestamp"):
        market_for(uni.drop(columns="timestamp"))
    bad = uni.copy()
    bad["timestamp"] = bad["timestamp"].astype(str)
    bad.loc[3, "timestamp"] = "not a date"
    with pytest.raises(ValueError, match="could not be parsed"):
        market_for(bad)


def test_duplicate_rows_fail_the_data_check(uni) -> None:
    doubled = pd.concat([uni, uni.iloc[:3]], ignore_index=True)
    report = verify_strategy(doubled, signals=np.zeros(len(doubled)))
    assert report["verdict"] == "REJECT" and report["checks"][0]["details"]["duplicate_timestamps"] == 3


def test_signals_table_is_matched_by_key(uni, tmp_path: Path) -> None:
    m = market_for(uni)
    weights = _momentum(m.frame)
    table = m.frame[["timestamp", "symbol"]].assign(signal=weights).sample(frac=1.0, random_state=1)
    path = tmp_path / "signals.csv"
    table.iloc[:-5].to_csv(path, index=False)  # missing rows are flat
    report = verify_strategy(uni, signals=str(path))
    direct = verify_strategy(uni, signals=np.where(np.isin(np.arange(len(weights)), table.index[-5:]), 0.0, weights))
    assert report["metrics"]["total_return"] == pytest.approx(direct["metrics"]["total_return"])
    assert recheck_certificate(report, uni, signals=str(path))["reproduced"]
    frame_table = m.frame[["timestamp", "symbol"]].assign(signal=weights)
    assert verify_strategy(uni, signals=frame_table)["metrics"]["total_return"] == pytest.approx(
        verify_strategy(uni, signals=weights)["metrics"]["total_return"]
    )
    keyless = tmp_path / "keyless.csv"
    pd.DataFrame({"signal": weights}).to_csv(keyless, index=False)  # row-aligned to the sorted table
    assert verify_strategy(uni, signals=str(keyless))["certificate_id"] == verify_strategy(uni, signals=weights)["certificate_id"]
    pd.DataFrame({"signal": weights[:10]}).to_csv(keyless, index=False)
    with pytest.raises(ValueError, match="one value per timestamp and symbol"):
        verify_strategy(uni, signals=str(keyless))
    with pytest.raises(ValueError, match="one value per timestamp and symbol"):
        verify_strategy(uni, signals=np.ones(10))
    twice = pd.concat([frame_table, frame_table.iloc[:1]])
    with pytest.raises(ValueError, match="duplicate"):
        verify_strategy(uni, signals=twice)


def test_recheck_and_grid(uni, tmp_path: Path) -> None:
    data = tmp_path / "universe.csv"
    uni.to_csv(data, index=False)
    strategy = TRAPS / "xs_momentum_rank.py"
    report = verify_strategy(data, strategy=strategy)
    assert recheck_certificate(report, data, strategy=strategy)["reproduced"]
    grid = verify_grid(data, {"lookback": [10, 20, 40]}, signal_fn=_momentum)
    assert grid["grid"]["n_combos"] == 3 and grid["reproducibility"]["universe"]["symbols"] == 6
    assert {c["id"] for c in grid["checks"]} >= {"walk_forward_oos", "parameter_plateau", "survivorship"}


def test_cli_and_mcp(uni, tmp_path: Path) -> None:
    data = tmp_path / "universe.csv"
    uni.to_csv(data, index=False)
    out = tmp_path / "cert.json"
    code = cli_main(["--ohlcv", str(data), "--strategy", str(TRAPS / "xs_next_return_rank.py"), "--out", str(out)])
    assert code == 2 and json.loads(out.read_text())["metrics"]["symbols"] == 6
    probe = tools.probe_lookahead(str(data), str(TRAPS / "xs_momentum_rank.py"))
    assert probe["truncation"]["status"] == "pass" and not probe["leak_detected"]  # probed as a universe
    leak = tools.probe_lookahead(str(data), str(TRAPS / "xs_next_return_rank.py"))
    assert leak["leak_detected"] and leak["truncation"]["mismatches"][0]["symbol"].startswith("S")
    stress = tools.cost_stress(str(data), strategy_path=str(TRAPS / "xs_momentum_rank.py"))
    assert stress["breakeven"]["breakeven_bps"] >= 0.0 and "1" in stress["delay"]["returns_by_delay"]
    res = tools.verify_strategy(str(data), strategy_path=str(TRAPS / "xs_momentum_rank.py"))
    assert res["reproducibility"]["universe"]["bars"] == 700 and "series" not in res


def test_weight_engine_values_a_new_listing_at_its_fill() -> None:
    # Regression: an instrument bought on its first bar had no close yet; valuing it made the
    # next order in the same bar NaN and the whole account NaN.
    a = np.array([10.0, 10.0, 10.0, 11.0, 11.0])
    b = np.array([np.nan, np.nan, 20.0, 20.0, 22.0])
    px = np.column_stack([a, b])
    w = np.array([[0.0, 0.5], [0.0, 0.5], [0.5, 0.5], [0.5, 0.5], [0.5, 0.5]])
    w[1] = [0.5, 0.5]  # both orders on the bar before b's first price
    out = run_weight_backtest(px, px, w, model=ExecutionModel(side_mode="long_short", commission_bps=0, slippage_bps=0, warmup_bars=0))
    assert np.isfinite(out["equity"]).all()
    assert out["total_return"] == pytest.approx(0.5 * 0.1 + 0.5 * 0.1)


def test_edges(monkeypatch) -> None:
    from monte_neo.verify import checks as rows
    from monte_neo.verify import timing

    one = rows.survivorship_row(["A"], np.array([0]), np.array([9]), 10)
    assert one["status"] == "skip"
    px = np.linspace(100, 120, 300)
    ohlc = {"open": px, "high": px, "low": px, "close": px}
    real = timing._terminal_return
    calls = {"n": 0}

    def first_only(o, s, m):  # the real run is finite, every shifted copy is not
        calls["n"] += 1
        return real(o, s, m) if calls["n"] == 1 else float("nan")

    monkeypatch.setattr(timing, "_terminal_return", first_only)
    res = timing.timing_significance(ohlc, np.ones(300, dtype=np.int64), ExecutionModel(warmup_bars=5))
    assert res["status"] == "skip" and res["n_shifts"] == 0
