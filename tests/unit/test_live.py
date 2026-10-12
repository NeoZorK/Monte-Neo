"""Family H: live vs backtest, implementation shortfall, alpha death monitor, live track needed, CLI."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli.monitor_cmd import main
from monte_neo.verify import verify_strategy
from monte_neo.verify.live import backtest_returns_from_certificate, load_live, verify_live
from monte_neo.verify.live_seq import cusum_alarm, live_track_needed, sprt_alarm

DAYS = pd.bdate_range("2020-01-01", periods=1200)
MU, SD = 0.004, 0.01


def _bt(seed: int = 0) -> pd.Series:
    return pd.Series(np.random.default_rng(seed).normal(MU, SD, 600), index=DAYS[:600], name="return")


def _live(mean: float, noise: float = 0.002, seed: int = 1, n: int = 600) -> pd.Series:
    bt = _bt()
    rng = np.random.default_rng(seed)
    base = bt.to_numpy()[:n] - MU + mean
    return pd.Series(base + rng.normal(0, noise, n), index=bt.index[:n], name="return")


def _status(rep: dict, cid: str) -> str:
    return next(c["status"] for c in rep["checks"] if c["id"] == cid)


def test_live_equal_to_backtest_no_warning() -> None:
    rep = verify_live(_bt(), _live(MU))
    assert rep["status"] == "ok" and rep["schema"] == "live-monitor/1"
    assert _status(rep, "live_vs_backtest") == "pass"
    assert rep["disclaimer"]


def test_edge_gone_triggers_alarm_and_warning() -> None:
    rep = verify_live(_bt(), _live(0.0))
    assert rep["status"] == "warn"
    assert _status(rep, "live_vs_backtest") == "warn"
    row = next(c for c in rep["checks"] if c["id"] == "alpha_death_monitor")
    assert row["status"] == "warn"
    assert row["details"]["cusum_alarm_date"] is not None
    assert row["details"]["haircut"] == 0.5
    assert pd.Timestamp(row["details"]["cusum_alarm_date"]) < DAYS[400]


def test_cusum_and_sprt_quiet_when_as_expected() -> None:
    r = np.random.default_rng(3).normal(MU, SD, 600)
    assert cusum_alarm(r, MU / 2, SD)[0] is None
    assert sprt_alarm(r, MU / 2, SD)[0] is None


def _fills(slip_bps: float, n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(5)
    ref = 100.0 + rng.normal(0, 1, n)
    side = np.where(np.arange(n) % 2 == 0, "buy", "sell")
    sign = np.where(side == "buy", 1.0, -1.0)
    px = ref * (1 + sign * slip_bps / 1e4)
    return pd.DataFrame({"timestamp": pd.date_range("2024-01-01", periods=n, freq="h"), "symbol": "AAA", "side": side,
                         "quantity": 1.0, "price": px, "reference_price": ref})


def test_fills_three_times_model_warns_with_recommendation() -> None:
    rep = verify_live(_bt(), load_live(_fills(15.0)), modelled_slippage_bps=5.0)
    row = next(c for c in rep["checks"] if c["id"] == "implementation_shortfall")
    assert row["status"] == "warn" and rep["status"] == "warn"
    assert row["details"]["recommended_slippage_bps"] == pytest.approx(15.0, abs=0.6)
    assert verify_live(_bt(), load_live(_fills(5.0)), modelled_slippage_bps=5.0)["status"] == "ok"


def test_fills_without_reference_skipped() -> None:
    rep = verify_live(_bt(), _live(MU), fills=_fills(1.0).drop(columns="reference_price"))
    assert _status(rep, "implementation_shortfall") == "skip"


def test_track_needed_math() -> None:
    expect = {"mean": 0.002, "std": 0.01, "skew": 0.0, "kurt": 3.0}
    row = live_track_needed(100, expect, 0.5)
    sr = 0.1
    need = int(np.ceil(1 + (1 + 2 * sr**2 / 4 * 1) * (1.6448536 / sr) ** 2))
    assert row["details"]["need_bars"] == pytest.approx(need, abs=1)
    assert row["details"]["bars_left"] == row["details"]["need_bars"] - 100


def test_load_live_detects_kind(tmp_path) -> None:
    f = tmp_path / "fills.csv"
    _fills(2.0).to_csv(f, index=False)
    r = tmp_path / "live.csv"
    _live(MU).rename_axis("date").reset_index().to_csv(r, index=False)
    assert load_live(f)["kind"] == "fills"
    assert load_live(r)["kind"] == "returns"


def test_certificate_series_extraction() -> None:
    df = synthetic_ohlcv(800, seed=1)
    sig = np.sign(df["close"].pct_change().fillna(0).rolling(5).mean().shift(1).fillna(0)).to_numpy()
    cert = verify_strategy(df, signals=sig)
    bt = backtest_returns_from_certificate(cert)
    assert len(bt) >= 100 and bt.index.is_monotonic_increasing
    assert len(bt.attrs["bars"]) == len(bt)
    assert sum(bt.attrs["bars"]) == pytest.approx(cert["series"]["bar"][-1] - cert["series"]["bar"][0])
    rep = verify_live(cert, _live(MU))
    assert rep["metrics"]["modelled_slippage_bps"] == 5.0


def test_cli_exit_codes(tmp_path, capsys) -> None:
    bt, ok, dead = tmp_path / "bt.csv", tmp_path / "ok.csv", tmp_path / "dead.csv"
    _bt().rename_axis("date").reset_index().to_csv(bt, index=False)
    _live(MU).rename_axis("date").reset_index().to_csv(ok, index=False)
    _live(0.0).rename_axis("date").reset_index().to_csv(dead, index=False)
    assert main(["--backtest", str(bt), "--live", str(ok)]) == 0
    assert main(["--backtest", str(bt), "--live", str(dead), "--out", str(tmp_path / "r.json")]) == 2
    assert (tmp_path / "r.json").exists()
    assert main(["--backtest", str(bt), "--live", str(tmp_path / "nope.csv")]) == 3
    assert main(["--live", str(ok)]) == 3
    capsys.readouterr()
    main(["--backtest", str(bt), "--live", str(ok), "--format", "json"])
    assert capsys.readouterr().out.strip().splitlines()[-1].startswith("Not investment advice")
