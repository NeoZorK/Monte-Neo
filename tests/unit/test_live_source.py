"""Live source and the ARL 9 gate: only real fills confirm; paper, testnet and simulated stop at 8."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.cli.monitor_cmd import main
from monte_neo.readiness import readiness
from monte_neo.verify.live import MIN_LIVE_BARS_REAL, MIN_REAL_FILLS, SOURCES, live_source_row, load_live, verify_live

DAYS = pd.bdate_range("2020-01-01", periods=400)
MU, SD = 0.004, 0.01


def _bt() -> pd.Series:
    return pd.Series(np.random.default_rng(0).normal(MU, SD, 300), index=DAYS[:300], name="return")


def _live(n: int = 300) -> pd.Series:
    bt = _bt()
    noise = np.random.default_rng(1).normal(0, 0.0003, n)
    return pd.Series(bt.to_numpy()[:n] + noise - noise.mean(), index=bt.index[:n], name="return")  # same mean: no drift to alarm on


def _fills(n: int = 40, slip_bps: float = 1.0) -> pd.DataFrame:
    ref = np.full(n, 100.0)
    return pd.DataFrame({"timestamp": pd.date_range("2020-01-01", periods=n, freq="D"), "symbol": "A", "side": "buy",
                         "quantity": 1.0, "price": ref * (1 + slip_bps / 1e4), "reference_price": ref})


def _row(rep: dict, cid: str = "live_source") -> dict:
    return next(c for c in rep["checks"] if c["id"] == cid)


def test_real_fills_with_enough_evidence_pass() -> None:
    rep = verify_live(_bt(), _live(), fills=_fills(), modelled_slippage_bps=2.0, source="real_fills")
    row = _row(rep)
    assert row["status"] == "pass" and rep["metrics"]["source"] == "real_fills" and "costs consistent" in row["summary"]
    assert rep["status"] == "ok"


@pytest.mark.parametrize("source", ["paper", "testnet", "simulated", None])
def test_other_sources_never_pass(source: str | None) -> None:
    rep = verify_live(_bt(), _live(), fills=_fills(), modelled_slippage_bps=2.0, source=source)
    row = _row(rep)
    assert row["status"] == "warn" and "stops at 8" in row["summary"]
    assert rep["status"] == "ok"  # the monitor itself is fine: only the ARL is limited
    assert any("ARL" in a or "real fills" in a for a in rep["next_actions"])
    if source == "testnet":
        assert "not that the orders are executable" in row["summary"]


def test_real_fills_but_too_little() -> None:
    short = _row(verify_live(_bt(), _live(40), fills=_fills(), modelled_slippage_bps=2.0, source="real_fills"))
    assert short["status"] == "warn" and "live bars" in short["summary"]
    few = _row(verify_live(_bt(), _live(), fills=_fills(MIN_REAL_FILLS - 1), modelled_slippage_bps=2.0, source="real_fills"))
    assert few["status"] == "warn" and "fills with a decision price" in few["summary"]
    none = _row(verify_live(_bt(), _live(), source="real_fills"))
    assert none["status"] == "warn" and "0 fills" in none["summary"]
    costly = _row(verify_live(_bt(), _live(), fills=_fills(slip_bps=20.0), modelled_slippage_bps=2.0, source="real_fills"))
    assert costly["status"] == "warn" and "within 1.5x" in costly["summary"]


def test_boundary_counts() -> None:
    ok = {"status": "pass", "details": {"n_fills": MIN_REAL_FILLS}}
    assert live_source_row("real_fills", MIN_LIVE_BARS_REAL, None, ok)["status"] == "pass"
    assert live_source_row("real_fills", MIN_LIVE_BARS_REAL - 1, None, ok)["status"] == "warn"
    assert live_source_row("real_fills", 100, 150, ok)["status"] == "warn"  # the track-record length can be longer than 60
    assert live_source_row("real_fills", 150, 150, ok)["status"] == "pass"
    assert live_source_row("real_fills", 100, None, {"status": "skip", "details": {}})["status"] == "warn"


def test_source_column_and_validation() -> None:
    df = pd.DataFrame({"date": DAYS[:30], "return": 0.001, "source": "paper"})
    assert load_live(df)["source"] == "paper"
    assert load_live(df.drop(columns="source"))["source"] is None
    assert load_live(pd.Series(0.001, DAYS[:30]))["source"] is None
    fills = _fills().assign(source="Real_Fills")
    assert load_live(fills)["source"] == "real_fills"
    with pytest.raises(ValueError, match="mixes live sources"):
        load_live(df.assign(source=["paper", "testnet"] * 15))
    with pytest.raises(ValueError, match="unknown live source"):
        load_live(df.assign(source="demo"))
    assert load_live(df.assign(source=None))["source"] is None  # empty column
    rep = verify_live(_bt(), df.assign(**{"return": _live(30).to_numpy(), "date": DAYS[:30]}))
    assert rep["metrics"]["source"] == "paper"
    with pytest.raises(ValueError, match="contradicts"):
        verify_live(_bt(), df, source="real_fills")
    with pytest.raises(ValueError, match="unknown live source"):
        verify_live(_bt(), df, source="demo")
    assert set(SOURCES) == {"real_fills", "paper", "testnet", "simulated"}


def _cert(live_source: str | None) -> dict:
    ids = ["data_integrity", "lookahead_truncation", "net_profitability", "timing_significance", "selection_adjusted_sharpe", "residual_alpha",
           "hidden_short_volatility", "deflated_sharpe", "market_impact", "synthetic_market_null", "universe_subsampling",
           "start_date_sensitivity", "rebalance_timing_luck", "marginal_sharpe", "live_vs_backtest", "alpha_death_monitor"]
    rows = [{"id": i, "status": "pass", "category": "x"} for i in ids]
    if live_source:
        rows.append({"id": "live_source", "status": live_source, "category": "integrity", "summary": "testnet: not executable proof"})
    return {"checks": rows}


def test_arl_nine_needs_real_fills() -> None:
    assert readiness(certificate=_cert("pass"))["level"] == 9
    paper = readiness(certificate=_cert("warn"))
    assert paper["level"] == 8 and "blocked at 9" in paper["summary"] and "testnet" in paper["summary"]
    assert readiness(certificate=_cert(None))["level"] == 8  # a live report without a source cannot confirm
    assert readiness(certificate=_cert(None))["levels"][8]["state"] == "not assessed"


def test_cli_source_flag(tmp_path, capsys) -> None:
    bt, live = tmp_path / "bt.csv", tmp_path / "live.csv"
    _bt().rename("return").rename_axis("date").to_csv(bt)
    _live().rename("return").rename_axis("date").to_csv(live)
    code = main(["--backtest", str(bt), "--live", str(live), "--source", "testnet", "--out", str(tmp_path / "o.json")])
    assert code in (0, 1, 2), capsys.readouterr().out
    assert '"source": "testnet"' in (tmp_path / "o.json").read_text()


def test_cli_text_report_prints_the_arl_headline(tmp_path, capsys) -> None:
    import json

    from monte_neo.backtest import synthetic_ohlcv
    from monte_neo.verify import verify_strategy

    df = synthetic_ohlcv(800, seed=1)
    sig = np.sign(df["close"].pct_change().fillna(0).rolling(5).mean().shift(1).fillna(0)).to_numpy()
    cert, live = tmp_path / "cert.json", tmp_path / "live.csv"
    cert.write_text(json.dumps(verify_strategy(df, signals=sig)), encoding="utf-8")
    _live().rename("return").rename_axis("date").to_csv(live)
    assert main(["--certificate", str(cert), "--live", str(live), "--source", "paper"]) in (0, 1)
    assert "ARL" in capsys.readouterr().out
