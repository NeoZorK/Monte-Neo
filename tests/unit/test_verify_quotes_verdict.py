"""verify_quotes certificate, its HTML section, `monte-neo verify --quotes` and the MCP tool."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.cli.verify_cmd import EXIT_CODES
from monte_neo.cli.verify_cmd import main as verify_main
from monte_neo.mcp import tools
from monte_neo.verify.quotes import load_quotes, make_grid, quote_quality, synthetic_quotes
from monte_neo.verify.quotes_verdict import recheck_quotes, verify_quotes
from monte_neo.verify.report_html import render_html
from monte_neo.verify.report_latency import latency_chart, latency_section
from monte_neo.verify.schema import VERDICT_SCHEMA_ID
from monte_neo.verify.verdict import model_from_costs

MODEL = model_from_costs(commission_bps=0.2, slippage_bps=0.0)
SLOW = "import numpy as np\ndef signal(df):\n    return np.sign(df['close'].diff(3).fillna(0.0).to_numpy())\n"
FAST = "import numpy as np\ndef signal(df):\n    return np.sign(df['close'].diff().fillna(0.0).to_numpy())\n"


def _slow(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["close"].diff(3).fillna(0.0).to_numpy())


def _fast(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["close"].diff().fillna(0.0).to_numpy())


@pytest.fixture(scope="module")
def slow_quotes() -> pd.DataFrame:
    return synthetic_quotes(40_000, rho=0.0, drift=1.5e-5, regime_steps=3000)


@pytest.fixture(scope="module")
def fast_quotes() -> pd.DataFrame:
    return synthetic_quotes(30_000, rho=0.5)


@pytest.fixture(scope="module")
def files(tmp_path_factory: pytest.TempPathFactory, slow_quotes: pd.DataFrame, fast_quotes: pd.DataFrame) -> dict[str, str]:
    d = tmp_path_factory.mktemp("quotes")
    slow_csv, fast_csv, parquet = d / "slow.csv", d / "fast.csv", d / "fast.parquet"
    slow_quotes.to_csv(slow_csv, index=False)
    fast_quotes.to_csv(fast_csv, index=False)
    fast_quotes.to_parquet(parquet)
    (d / "slow.py").write_text(SLOW)
    (d / "fast.py").write_text(FAST)
    paths = {"slow_csv": slow_csv, "fast_csv": fast_csv, "parquet": parquet, "slow_py": d / "slow.py", "fast_py": d / "fast.py", "dir": d}
    return {k: str(v) for k, v in paths.items()}


def test_honest_strategy_passes(slow_quotes: pd.DataFrame) -> None:
    report = verify_quotes(slow_quotes, signal_fn=_slow, bar_ms=1000.0, model=MODEL, samples=8)
    assert report["schema"] == VERDICT_SCHEMA_ID and report["verdict"] == "PASS"
    ids = {c["id"] for c in report["checks"]}
    assert ids == {"quote_quality", "net_profitability", "arrival_lookahead", "latency_tolerance", "latency_monte_carlo"}
    assert report["metrics"]["return_arrival_clock"] > 0
    assert report["reproducibility"]["settings"]["kind"] == "quotes"


def test_strategy_that_needs_data_before_it_arrived_gets_a_warning(fast_quotes: pd.DataFrame) -> None:
    report = verify_quotes(fast_quotes, signal_fn=_fast, bar_ms=10.0, model=MODEL, samples=4)
    assert report["verdict"] == "PASS_WITH_WARNINGS"
    assert any(c["id"] == "arrival_lookahead" and c["status"] == "warn" for c in report["checks"])
    assert report["next_actions"]


def test_losing_strategy_is_rejected_like_in_verify_strategy(fast_quotes: pd.DataFrame) -> None:
    report = verify_quotes(fast_quotes, signal_fn=_fast, bar_ms=10.0, samples=2)  # default costs eat a 10 ms strategy
    assert report["verdict"] == "REJECT"
    assert next(c for c in report["checks"] if c["id"] == "net_profitability")["status"] == "fail"


def test_certificate_id_is_reproducible_and_depends_on_the_data(slow_quotes: pd.DataFrame) -> None:
    a = verify_quotes(slow_quotes, signal_fn=_slow, bar_ms=1000.0, model=MODEL, samples=4)
    b = verify_quotes(slow_quotes, signal_fn=_slow, bar_ms=1000.0, model=MODEL, samples=4)
    c = verify_quotes(slow_quotes.iloc[:30_000], signal_fn=_slow, bar_ms=1000.0, model=MODEL, samples=4)
    assert a["certificate_id"] == b["certificate_id"] != c["certificate_id"]


def test_too_few_bars_is_a_clear_error(fast_quotes: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="record longer or use a shorter bar_ms"):
        verify_quotes(fast_quotes.iloc[:200], signal_fn=_fast, bar_ms=1000.0, model=MODEL)


def test_costs_and_warmup_can_be_given_without_a_model(fast_quotes: pd.DataFrame) -> None:
    report = verify_quotes(fast_quotes.iloc[:6000], signal_fn=_fast, bar_ms=50.0, commission_bps=0.2, slippage_bps=0.0, warmup_bars=7, samples=2)
    model = report["reproducibility"]["model"]
    assert model["commission_bps"] == 0.2 and model["slippage_bps"] == 0.0 and model["warmup_bars"] == 7
    default = verify_quotes(fast_quotes.iloc[:6000], signal_fn=_fast, bar_ms=50.0, samples=2)
    n_bars = make_grid(load_quotes(fast_quotes.iloc[:6000]), 50.0).n_bars
    assert default["reproducibility"]["model"]["warmup_bars"] == min(60, n_bars // 10)


def test_needs_exactly_one_strategy_source(slow_quotes: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        verify_quotes(slow_quotes)
    with pytest.raises(ValueError, match="exactly one"):
        verify_quotes(slow_quotes, strategy="x.py", signal_fn=_slow)


def test_reads_csv_parquet_and_a_strategy_file(files: dict[str, str]) -> None:
    from_csv = verify_quotes(files["fast_csv"], strategy=files["fast_py"], bar_ms=10.0, model=MODEL, samples=3)
    from_parquet = verify_quotes(files["parquet"], strategy=files["fast_py"], bar_ms=10.0, model=MODEL, samples=3)
    assert from_csv["reproducibility"]["source_sha256"] and from_csv["verdict"] == from_parquet["verdict"]
    assert from_csv["metrics"]["return_exchange_clock"] == pytest.approx(from_parquet["metrics"]["return_exchange_clock"], abs=1e-9)


def test_csv_timestamps_with_and_without_fractions_are_all_kept(tmp_path: Path) -> None:
    """Regression: a format guessed from the first row turned later rows into NaT and dropped them silently."""
    df = synthetic_quotes(50)
    df["timestamp"] = df["timestamp"].astype(str)
    df.loc[0, "timestamp"] = "2025-10-02 00:00:00+00:00"  # no fraction, like the first row of many exports
    path = tmp_path / "q.csv"
    df.to_csv(path, index=False)
    q = load_quotes(pd.read_csv(path))
    assert len(q) == 50 and q.dropped == 0


def test_unparseable_rows_are_counted_and_warned() -> None:
    df = synthetic_quotes(40)
    df["timestamp"] = df["timestamp"].astype(str)
    df.loc[3, "timestamp"] = "garbage"
    info = quote_quality(load_quotes(df))
    assert info["dropped_rows"] == 1 and info["status"] == "warn"


def test_html_shows_the_latency_section_without_equity(fast_quotes: pd.DataFrame) -> None:
    report = verify_quotes(fast_quotes, signal_fn=_fast, bar_ms=50.0, model=MODEL, samples=4)
    page = render_html(report)
    assert "Time and latency" in page and "<polyline" in page and "verify --quotes" in page
    assert "<h2>Equity</h2>" not in page and "<h2>Summary</h2>" not in page


def test_latency_section_is_empty_for_ordinary_certificates_and_survives_bad_input() -> None:
    assert latency_section({}) == "" and latency_section({"latency": "x"}) == ""
    assert latency_chart({"return_by_extra_ms": {"0": 0.1}}) == ""
    assert latency_chart({"return_by_extra_ms": {"a": 1.0, "0": float("nan"), "5": 0.1}}) == ""
    junk = latency_section({"latency": {"arrival": {}, "scan": {"return_by_extra_ms": "x"}, "monte_carlo": {}, "quality": {}}})
    assert "Time and latency" in junk and "—" in junk
    chart = latency_chart({"return_by_extra_ms": {"0": 0.1, "50": -0.1}, "p95_latency_ms": 20.0})
    assert "observed p95" in chart and "<script" not in chart


def test_cli_demo_and_quotes_run(files: dict[str, str], capsys: pytest.CaptureFixture[str]) -> None:
    assert verify_main(["--demo-quotes"]) == 0
    assert "PASS_WITH_WARNINGS" in capsys.readouterr().out
    out = Path(files["dir"]) / "cert.json"
    html = Path(files["dir"]) / "cert.html"
    code = verify_main([
        "--quotes", files["fast_csv"], "--strategy", files["fast_py"], "--bar-ms", "10", "--commission-bps", "0.2",
        "--slippage-bps", "0", "--latency-samples", "3", "--out", str(out), "--html", str(html),
    ])
    cert = json.loads(out.read_text())
    assert code == EXIT_CODES[cert["verdict"]] and cert["verdict"] == "PASS_WITH_WARNINGS"
    assert cert["schema"] == VERDICT_SCHEMA_ID and "Time and latency" in html.read_text()
    assert "exchange clock" in capsys.readouterr().out


def test_cli_quotes_errors_are_not_verdicts(files: dict[str, str], capsys: pytest.CaptureFixture[str]) -> None:
    assert verify_main(["--quotes", files["fast_csv"]]) == 3
    assert "needs --strategy" in capsys.readouterr().out
    assert verify_main(["--quotes", str(Path(files["dir"]) / "missing.csv"), "--strategy", files["fast_py"]]) == 3
    assert "verify failed" in capsys.readouterr().out


def test_mcp_tool_returns_a_compact_certificate(files: dict[str, str]) -> None:
    compact = tools.verify_quotes(files["fast_csv"], files["fast_py"], bar_ms=10.0, commission_bps=0.2, latency_samples=3)
    assert compact["schema"] == VERDICT_SCHEMA_ID
    assert all("details" not in c for c in compact["checks"] if c["status"] not in ("fail", "warn"))
    full = tools.verify_quotes(files["fast_csv"], files["fast_py"], bar_ms=10.0, commission_bps=0.2, latency_samples=3, compact=False)
    assert all("details" in c for c in full["checks"])
    assert tools.verify_quotes in tools.TOOLS
    assert "verify_quotes" in tools.SERVER_INSTRUCTIONS


def test_verify_quotes_is_a_lazy_public_name() -> None:
    import monte_neo.verify as v

    assert v.verify_quotes is verify_quotes and "verify_quotes" in v.__all__


def test_verify_quotes_picks_one_symbol_and_records_it(fast_quotes: pd.DataFrame) -> None:
    other = synthetic_quotes(500, seed=9)
    other["symbol"] = "OTHER@SIM"
    table = pd.concat([fast_quotes, other], ignore_index=True)
    with pytest.raises(ValueError, match="2 symbols"):
        verify_quotes(table, signal_fn=_fast, bar_ms=50.0, model=MODEL, samples=2)
    report = verify_quotes(table, signal_fn=_fast, bar_ms=50.0, model=MODEL, samples=2, symbol="SYN-USDT@SIM")
    assert report["reproducibility"]["settings"]["symbol"] == "SYN-USDT@SIM"
    alone = verify_quotes(fast_quotes, signal_fn=_fast, bar_ms=50.0, model=MODEL, samples=2, symbol="SYN-USDT@SIM")
    assert report["reproducibility"]["data_sha256"] == alone["reproducibility"]["data_sha256"]


def test_order_latency_is_in_the_certificate_and_the_profit_line(fast_quotes: pd.DataFrame) -> None:
    report = verify_quotes(fast_quotes, signal_fn=_fast, bar_ms=50.0, model=MODEL, samples=2, order_latency_ms=100.0)
    assert report["reproducibility"]["settings"]["order_latency_ms"] == 100.0 and report["metrics"]["order_latency_ms"] == 100.0
    assert "100 ms order delay" in next(c for c in report["checks"] if c["id"] == "net_profitability")["summary"]
    with pytest.raises(ValueError, match="order_latency_ms"):
        verify_quotes(fast_quotes, signal_fn=_fast, bar_ms=50.0, model=MODEL, order_latency_ms=-1.0)


def test_recheck_reproduces_a_quote_certificate_and_catches_changed_inputs(files: dict[str, str], fast_quotes: pd.DataFrame) -> None:
    report = verify_quotes(files["fast_csv"], strategy=files["fast_py"], bar_ms=50.0, model=MODEL, samples=3, order_latency_ms=20.0)
    ok = recheck_quotes(report, files["fast_csv"], strategy=files["fast_py"])
    assert ok["reproduced"] is True and ok["verdict_matches"] and ok["certificate_id_matches"]
    assert ok["inputs_match"] == {"data_sha256": True, "source_sha256": True}
    changed = fast_quotes.copy()
    changed.loc[5, "bid"] *= 1.5
    bad_data = recheck_quotes(report, changed, strategy=files["fast_py"])
    assert bad_data["reproduced"] is False and bad_data["reason"] == "inputs differ from the certificate"
    Path(files["dir"], "other.py").write_text(SLOW)
    bad_code = recheck_quotes(report, files["fast_csv"], strategy=str(Path(files["dir"]) / "other.py"))
    assert bad_code["inputs_match"]["source_sha256"] is False and bad_code["reproduced"] is False
    older = json.loads(json.dumps(report))
    older["reproducibility"]["engine_version"] = "v0.0.1"
    older["certificate_id"] = "0123456789abcdef"  # an older engine produced another id
    stale = recheck_quotes(older, files["fast_csv"], strategy=files["fast_py"])
    assert stale["reproduced"] is False and "v0.0.1" in stale["reason"]
    tampered = json.loads(json.dumps(report))
    tampered["verdict"] = "PASS"
    assert recheck_quotes(tampered, files["fast_csv"], strategy=files["fast_py"])["reason"] == "verdict differs"


def test_recheck_refuses_an_ohlcv_certificate_and_a_signal_function_source(files: dict[str, str], fast_quotes: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="not a quote certificate"):
        recheck_quotes({"schema": VERDICT_SCHEMA_ID, "reproducibility": {"settings": {}}}, files["fast_csv"], strategy=files["fast_py"])
    report = verify_quotes(fast_quotes, signal_fn=_fast, bar_ms=50.0, model=MODEL, samples=2)
    same = recheck_quotes(report, fast_quotes, signal_fn=_fast)
    assert same["inputs_match"]["source_sha256"] is True and same["reproduced"] is True


def test_cli_recheck_and_the_new_options(files: dict[str, str], capsys: pytest.CaptureFixture[str]) -> None:
    cert = Path(files["dir"]) / "cert50.json"
    args = ["--quotes", files["fast_csv"], "--strategy", files["fast_py"], "--bar-ms", "50", "--commission-bps", "0.2",
            "--slippage-bps", "0", "--latency-samples", "2", "--symbol", "SYN-USDT@SIM", "--order-latency-ms", "20"]
    verify_main([*args, "--out", str(cert)])
    capsys.readouterr()
    assert verify_main(["--recheck", str(cert), "--quotes", files["fast_csv"], "--strategy", files["fast_py"]]) == 0
    assert '"reproduced": true' in capsys.readouterr().out
    other = Path(files["dir"]) / "other_quotes.csv"
    pd.read_csv(files["fast_csv"]).iloc[:-50].to_csv(other, index=False)
    assert verify_main(["--recheck", str(cert), "--quotes", str(other), "--strategy", files["fast_py"]]) == 4
    capsys.readouterr()
    assert verify_main(["--recheck", str(Path(files["dir"]) / "missing.json"), "--quotes", files["fast_csv"], "--strategy", files["fast_py"]]) == 3
    assert "recheck failed" in capsys.readouterr().out
    assert verify_main(["--recheck", str(cert), "--quotes", files["fast_csv"]]) == 3  # needs --strategy
    capsys.readouterr()


def test_mcp_recheck_takes_quotes(files: dict[str, str]) -> None:
    cert = Path(files["dir"]) / "mcp_cert.json"
    report = tools.verify_quotes(files["fast_csv"], files["fast_py"], bar_ms=50.0, commission_bps=0.2, latency_samples=2,
                                 symbol="SYN-USDT@SIM", order_latency_ms=10.0, compact=False)
    cert.write_text(json.dumps(report))
    out = tools.recheck_certificate(str(cert), quotes_path=files["fast_csv"], strategy_path=files["fast_py"])
    assert out["reproduced"] is True
    assert "error" in tools.recheck_certificate(str(cert), quotes_path=files["fast_csv"])
    assert "error" in tools.recheck_certificate(str(cert))
