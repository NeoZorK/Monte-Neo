"""Self-contained HTML report of a certificate."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli.verify_cmd import main as cli_main
from monte_neo.mcp import tools
from monte_neo.verify import verify_grid, verify_strategy
from monte_neo.verify.report_html import VERIFY_PAGE, render_html


@pytest.fixture(scope="module")
def report() -> dict:
    df = synthetic_ohlcv(1500, seed=13)
    return verify_strategy(df, signals=(df["close"] > df["close"].rolling(30).mean()).astype(int).to_numpy())


def _no_active_content(page: str) -> None:
    assert "<script" not in page.lower() and "javascript:" not in page.lower()
    links = set(re.findall(r'(?:href|src)="([^"]+)"', page))
    assert links <= {VERIFY_PAGE}  # nothing is loaded from the network


def test_page_structure(report) -> None:
    page = render_html(report)
    _no_active_content(page)
    assert page.startswith("<!doctype html>") and page.count("<svg") == 2
    assert f"Monte-Neo verdict {report['verdict']}" in page and report["certificate_id"] in page
    for check in report["checks"]:
        assert check["id"] in page
    for period in report["breakdown"]["periods"]:
        assert period["period"] in page
    assert "Not signed" in page and "By market regime" in page


def test_text_from_the_certificate_is_escaped(report) -> None:
    evil = json.loads(json.dumps(report))
    evil["checks"][0]["summary"] = '<script>alert(1)</script> "x" & y'
    evil["next_actions"] = ["<img src=x onerror=alert(1)>"]
    page = render_html(evil)
    _no_active_content(page)
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &quot;x&quot; &amp; y" in page
    assert "&lt;img src=x onerror=alert(1)&gt;" in page


def test_signed_grid_and_universe_sections(report) -> None:
    signed = dict(report, signature={"alg": "ed25519", "key_id": "abcd1234abcd1234", "public_key": "k", "value": "v"})
    assert "abcd1234abcd1234" in render_html(signed) and VERIFY_PAGE in render_html(signed)
    df = synthetic_ohlcv(1200, seed=2)
    grid = verify_grid(df, {"n": [10, 20]}, signal_fn=lambda d, n=10: (d["close"] > d["close"].rolling(n).mean()).astype(int))
    assert "Parameter search" in render_html(grid)
    universe = dict(report, reproducibility={**report["reproducibility"], "universe": {"symbols": 7, "bars": 10}})
    assert ">7</b>" in render_html(universe)


def test_minimal_certificate() -> None:
    page = render_html({"verdict": "REJECT", "checks": [], "metrics": {}, "reproducibility": {}})
    assert "No equity series" in page and "What to fix" not in page and "—" in page
    tiny = render_html({"verdict": "PASS", "series": {"bar": [0, 1], "time": None, "equity": [1.0, 1.0], "benchmark": [1.0, 1.0]}})
    assert "bar 0" in tiny and "bar 1" in tiny


def test_cli_and_mcp(report, tmp_path: Path) -> None:
    df = synthetic_ohlcv(900, seed=3)
    data = tmp_path / "prices.csv"
    df.to_csv(data, index=False)
    np.save(tmp_path / "sig.npy", np.sign(df["close"].diff().fillna(0)).to_numpy())
    cert, page = tmp_path / "cert.json", tmp_path / "report.html"
    code = cli_main(["--ohlcv", str(data), "--signals", str(tmp_path / "sig.npy"), "--out", str(cert), "--html", str(page)])
    assert code in (0, 1, 2) and page.read_text(encoding="utf-8").startswith("<!doctype html>")
    again = tmp_path / "again.html"
    assert cli_main(["--render", str(cert), "--html", str(again)]) == 0
    assert again.read_text(encoding="utf-8") == page.read_text(encoding="utf-8")
    assert cli_main(["--render", str(cert)]) == 3  # needs --html
    (tmp_path / "bad.json").write_text("{}", encoding="utf-8")
    assert cli_main(["--render", str(tmp_path / "bad.json"), "--html", str(again)]) == 3
    out = tools.render_report(str(cert), str(tmp_path / "mcp.html"))
    assert out["bytes"] > 1000 and Path(out["html_path"]).is_file()
    assert "error" in tools.render_report(str(tmp_path / "bad.json"), str(tmp_path / "x.html"))


def test_percent_formatting_handles_missing_values(report) -> None:
    broken = dict(report, metrics={**report["metrics"], "total_return": float("nan"), "max_drawdown": None})
    page = render_html(broken)
    assert "nan%" not in page.lower() and "<b>nan" not in page.lower()
    assert "<b>—</b>" in page
