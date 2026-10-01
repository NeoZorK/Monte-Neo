"""Several feeds in one strategy, assumed latency models, the spread check, the look-ahead probes on arrival bars."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.cli.verify_cmd import main as verify_main
from monte_neo.mcp import tools
from monte_neo.verify.quotes import (
    QuoteSet,
    as_set,
    assume_latency,
    feed_alias,
    info_bars,
    load_quotes,
    make_grid,
    parse_latency_model,
    select_symbol,
    synthetic_feeds,
    synthetic_quotes,
)
from monte_neo.verify.quotes_verdict import assumptions, recheck_quotes, spread_info, spread_row, verify_quotes
from monte_neo.verify.report_html import render_html
from monte_neo.verify.verdict import model_from_costs

MODEL = model_from_costs(commission_bps=0.1, slippage_bps=0.15)
FOLLOW = "import numpy as np\ndef signal(df):\n    return np.sign(df['LEAD_SIM_close'].diff(3).fillna(0.0).to_numpy())\n"


def follow(df: pd.DataFrame) -> np.ndarray:
    """Trade LAG on the move of LEAD (the follower repeats the leader 30 ms later)."""
    return np.sign(df["LEAD_SIM_close"].diff(3).fillna(0.0).to_numpy())


def foresight(df: pd.DataFrame) -> np.ndarray:
    """Reads the next bar's close: a leak that exists on every clock."""
    return np.sign(df["close"].shift(-1) - df["close"]).fillna(0.0).to_numpy()


def _status(report: dict, check_id: str) -> str:
    return next(c["status"] for c in report["checks"] if c["id"] == check_id)


@pytest.fixture(scope="module")
def feeds_fast() -> pd.DataFrame:
    return synthetic_feeds(20_000, leader_latency_ms=2.0, follower_latency_ms=2.0)


@pytest.fixture(scope="module")
def feeds_late_leader() -> pd.DataFrame:
    return synthetic_feeds(20_000, leader_latency_ms=80.0, follower_latency_ms=2.0)


# --- latency models -------------------------------------------------------------------------------------------------


def test_latency_model_specs_are_parsed_and_bad_ones_named() -> None:
    assert parse_latency_model("constant:5") == ("constant", 5.0, 5.0)
    assert parse_latency_model("lognormal:8,25") == ("lognormal", 8.0, 25.0)
    for bad in ("lognormal:25,8", "lognormal:8", "constant:-1", "constant:", "gauss:1,2", "constant:x"):
        with pytest.raises(ValueError, match="latency model"):
            parse_latency_model(bad)


def test_assumed_latency_has_the_asked_median_and_p95_and_is_reproducible() -> None:
    q = load_quotes(synthetic_quotes(20_000))
    a = assume_latency(q, "lognormal:8,25", seed=3)
    assert np.median(a.latency_ms) == pytest.approx(8.0, rel=0.05) and np.percentile(a.latency_ms, 95) == pytest.approx(25.0, rel=0.08)
    assert np.array_equal(a.latency_ms, assume_latency(q, "lognormal:8,25", seed=3).latency_ms)
    assert not np.array_equal(a.latency_ms, assume_latency(q, "lognormal:8,25", seed=3, salt="other").latency_ms)
    assert set(assume_latency(q, "constant:7").latency_ms) == {7.0}
    assert np.array_equal(a.bid, q.bid) and np.array_equal(a.exchange_ns, q.exchange_ns)


def test_a_table_without_latency_needs_a_model() -> None:
    table = synthetic_quotes(500).drop(columns=["latency_ms"])
    with pytest.raises(ValueError, match="assumed latency model"):
        load_quotes(table)
    assert set(load_quotes(table, allow_missing_latency=True).latency_ms) == {0.0}


def test_verify_quotes_with_an_assumed_latency_says_so(tmp_path: Path) -> None:
    table = synthetic_quotes(30_000, rho=0.5).drop(columns=["latency_ms"])
    report = verify_quotes(table, signal_fn=lambda d: np.sign(d["close"].diff().fillna(0.0).to_numpy()), bar_ms=50.0,
                           model=MODEL, samples=3, latency_model="lognormal:20,54", probes=False)
    assert report["reproducibility"]["settings"]["latency_model"] == "lognormal:20,54"
    assert any("ASSUMED" in line for line in report["assumptions"])
    assert 15 < report["metrics"]["latency_p50_ms"] < 25
    with pytest.raises(ValueError, match="assumed latency model"):
        verify_quotes(table, signal_fn=follow, bar_ms=50.0, model=MODEL)


# --- several feeds ---------------------------------------------------------------------------------------------------


def test_feed_alias_quote_set_and_info_bars() -> None:
    assert feed_alias("ETH-USDT@X") == "ETH_USDT_X"
    table = load_quotes(synthetic_feeds(2_000))
    main, lead = select_symbol(table, "LAG@SIM"), select_symbol(table, "LEAD@SIM")
    qs = QuoteSet(main, (("LEAD_SIM", lead),))
    assert as_set(main).others == () and as_set(qs) is qs and len(qs) == len(main)
    assert [a for a, _ in qs.feeds] == ["", "LEAD_SIM"] and len(qs.latency_ms) == len(main) + len(lead)
    grid = make_grid(qs, 10.0, max_extra_ms=50.0)
    bars = info_bars(qs, grid, clock="arrival")
    assert {"open", "close", "volume", "LEAD_SIM_open", "LEAD_SIM_close", "LEAD_SIM_volume"} <= set(bars)
    forced = info_bars(qs, grid, clock="arrival", latency_overrides={"LEAD_SIM": np.zeros(len(lead))})
    assert np.array_equal(forced["LEAD_SIM_close"], info_bars(qs, grid, clock="exchange")["LEAD_SIM_close"])
    assert np.array_equal(forced["close"], bars["close"])


def test_synthetic_feeds_follower_repeats_the_leader_later() -> None:
    table = synthetic_feeds(5_000, lead_ms=30.0, step_ms=10.0)
    lead = table[table.symbol == "LEAD@SIM"].reset_index(drop=True)
    lag = table[table.symbol == "LAG@SIM"].reset_index(drop=True)
    assert set(table.symbol) == {"LEAD@SIM", "LAG@SIM"} and len(lead) == len(lag) == 5_000
    r_lead, r_lag = np.diff(np.log(lead.bid)), np.diff(np.log(lag.bid))
    assert np.corrcoef(r_lead[:-3], r_lag[3:])[0, 1] > 0.9 > abs(np.corrcoef(r_lead, r_lag)[0, 1]) + 0.5


def test_a_leader_that_arrives_late_makes_the_edge_vanish(feeds_fast: pd.DataFrame, feeds_late_leader: pd.DataFrame) -> None:
    kw = {"signal_fn": follow, "symbol": "LAG@SIM", "feeds": ["LEAD@SIM"], "bar_ms": 10.0, "model": MODEL, "samples": 4, "probes": False}
    quick = verify_quotes(feeds_fast, **kw)
    late = verify_quotes(feeds_late_leader, **kw)
    assert quick["verdict"] == "PASS" and quick["metrics"]["return_arrival_clock"] > 0
    assert _status(late, "arrival_lookahead") == "warn" and late["metrics"]["return_arrival_clock"] < 0 < late["metrics"]["return_exchange_clock"]
    assert late["reproducibility"]["settings"]["feeds"] == ["LEAD@SIM"]
    assert any("other feed" in line for line in late["assumptions"])


def test_feed_arguments_are_checked(feeds_fast: pd.DataFrame) -> None:
    kw = {"signal_fn": follow, "bar_ms": 10.0, "model": MODEL, "samples": 2, "probes": False}
    with pytest.raises(ValueError, match="need symbol"):
        verify_quotes(feeds_fast, feeds=["LEAD@SIM"], **kw)
    with pytest.raises(ValueError, match="other symbols"):
        verify_quotes(feeds_fast, symbol="LAG@SIM", feeds=["LAG@SIM"], **kw)
    with pytest.raises(ValueError, match="other symbols"):
        verify_quotes(feeds_fast, symbol="LAG@SIM", feeds=["LEAD@SIM", "LEAD@SIM"], **kw)
    clash = pd.concat([feeds_fast, feeds_fast.assign(symbol=lambda d: d["symbol"].map({"LEAD@SIM": "close", "LAG@SIM": "LAG@SIM"}))])
    with pytest.raises(ValueError, match="other symbols"):
        verify_quotes(clash, symbol="LAG@SIM", feeds=["close"], **kw)


def test_a_broken_feed_is_named_in_the_quality_row(feeds_fast: pd.DataFrame) -> None:
    broken = feeds_fast.copy()
    mask = broken.symbol == "LEAD@SIM"
    broken.loc[mask, "bid"] = broken.loc[mask, "ask"] * 1.01  # every leader quote crossed
    report = verify_quotes(broken, signal_fn=follow, symbol="LAG@SIM", feeds=["LEAD@SIM"], bar_ms=10.0, model=MODEL, samples=2, probes=False)
    row = next(c for c in report["checks"] if c["id"] == "quote_quality")
    assert row["status"] == "warn" and "LEAD_SIM" in row["summary"] and row["details"]["feeds"]["LEAD_SIM"]["status"] == "warn"


def test_recheck_reproduces_a_multi_feed_certificate_with_an_assumed_latency(feeds_fast: pd.DataFrame, tmp_path: Path) -> None:
    table = feeds_fast.drop(columns=["latency_ms"])
    (tmp_path / "follow.py").write_text(FOLLOW)
    kw = {"symbol": "LAG@SIM", "feeds": ["LEAD@SIM"], "bar_ms": 10.0, "model": MODEL, "samples": 3, "latency_model": "lognormal:3,9", "probes": False}
    cert = verify_quotes(table, strategy=str(tmp_path / "follow.py"), **kw)
    again = recheck_quotes(cert, table, strategy=str(tmp_path / "follow.py"))
    assert again["reproduced"] is True and again["inputs_match"] == {"data_sha256": True, "source_sha256": True}
    shifted = table.copy()
    shifted.loc[shifted.symbol == "LEAD@SIM", "bid"] *= 1.001
    assert recheck_quotes(cert, shifted, strategy=str(tmp_path / "follow.py"))["inputs_match"]["data_sha256"] is False


# --- the spread check and the assumptions ---------------------------------------------------------------------------


def test_spread_row_compares_the_model_with_the_half_spread() -> None:
    q = load_quotes(synthetic_quotes(2_000))
    info = spread_info(q)
    assert info["median_bps"] == pytest.approx(0.1, rel=0.01) and info["p95_bps"] >= info["median_bps"]
    thin = spread_row(info, model_from_costs(commission_bps=0.2, slippage_bps=0.0))
    covered = spread_row(info, model_from_costs(commission_bps=0.2, slippage_bps=0.2))
    assert thin["status"] == "warn" and "below" in thin["summary"] and covered["status"] == "pass" and "covers" in covered["summary"]


def test_assumptions_name_what_is_not_modelled() -> None:
    lines = assumptions(MODEL, 20.0, None, [])
    text = " ".join(lines)
    assert "no queue position" in text and "20 ms" in text and "recorded in the quotes" in text and "ASSUMED" not in text
    assert any("ASSUMED (constant:5)" in x for x in assumptions(MODEL, 0.0, "constant:5", []))


def test_the_report_shows_the_assumptions_and_the_spread() -> None:
    report = verify_quotes(synthetic_quotes(30_000, rho=0.5), signal_fn=lambda d: np.sign(d["close"].diff().fillna(0.0).to_numpy()),
                           bar_ms=50.0, model=MODEL, samples=2, probes=False)
    page = render_html(report)
    assert "What this run assumes" in page and "no queue position" in page and "half-spread" in page
    assert report["metrics"]["half_spread_bps"] == pytest.approx(0.1, rel=0.02)


# --- the look-ahead probes on the arrival bars ---------------------------------------------------------------------------


def test_a_strategy_that_reads_the_next_bar_is_rejected_by_the_probes() -> None:
    quotes = synthetic_quotes(20_000, rho=0.0, drift=4e-6, regime_steps=3000)
    leaky = verify_quotes(quotes, signal_fn=foresight, bar_ms=1000.0, model=MODEL, samples=2)
    assert leaky["verdict"] == "REJECT" and _status(leaky, "lookahead_truncation") == "fail"
    assert _status(leaky, "arrival_lookahead") != "fail"  # the clock check alone does not see this leak
    skipped = verify_quotes(quotes, signal_fn=foresight, bar_ms=1000.0, model=MODEL, samples=2, probes=False)
    assert "lookahead_truncation" not in {c["id"] for c in skipped["checks"]}
    assert skipped["reproducibility"]["settings"]["probes"] is False and leaky["reproducibility"]["settings"]["probes"] is True


# --- CLI and MCP -----------------------------------------------------------------------------------------------------


def test_cli_feeds_latency_model_and_no_probes(tmp_path: Path, feeds_fast: pd.DataFrame, capsys: pytest.CaptureFixture[str]) -> None:
    quotes, strat, cert = tmp_path / "q.csv", tmp_path / "follow.py", tmp_path / "cert.json"
    feeds_fast.drop(columns=["latency_ms"]).to_csv(quotes, index=False)
    strat.write_text(FOLLOW)
    args = ["--quotes", str(quotes), "--strategy", str(strat), "--bar-ms", "10", "--commission-bps", "0.1", "--slippage-bps", "0.15",
            "--latency-samples", "2", "--symbol", "LAG@SIM", "--feeds", "LEAD@SIM", "--latency-model", "constant:3", "--no-probes"]
    code = verify_main([*args, "--out", str(cert)])
    out = capsys.readouterr().out
    saved = json.loads(cert.read_text())
    assert code == 0 and "assumes:" in out and saved["reproducibility"]["settings"]["feeds"] == ["LEAD@SIM"]
    assert saved["reproducibility"]["settings"]["latency_model"] == "constant:3" and saved["reproducibility"]["settings"]["probes"] is False
    assert verify_main(["--recheck", str(cert), "--quotes", str(quotes), "--strategy", str(strat)]) == 0
    capsys.readouterr()


def test_mcp_tool_takes_feeds_and_a_latency_model(tmp_path: Path, feeds_fast: pd.DataFrame) -> None:
    quotes, strat = tmp_path / "q.csv", tmp_path / "follow.py"
    feeds_fast.drop(columns=["latency_ms"]).to_csv(quotes, index=False)
    strat.write_text(FOLLOW)
    out = tools.verify_quotes(str(quotes), str(strat), bar_ms=10.0, commission_bps=0.1, slippage_bps=0.15, latency_samples=2,
                              symbol="LAG@SIM", feeds=["LEAD@SIM"], latency_model="constant:3", probes=False)
    assert out["verdict"] in ("PASS", "PASS_WITH_WARNINGS") and out["reproducibility"]["settings"]["feeds"] == ["LEAD@SIM"]
