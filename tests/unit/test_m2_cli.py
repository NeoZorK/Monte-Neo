"""CLI and MCP wiring of M2: verify --returns / --events, alpha with book and factor families, MCP tools."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from monte_neo.alpha import validate_alpha
from monte_neo.alpha.report import demo_panel
from monte_neo.cli import verify_cmd
from monte_neo.mcp import tools
from monte_neo.verify.returns_dd import demo_returns


def _returns_file(tmp_path: Path, name: str) -> Path:
    path = tmp_path / f"{name}.csv"
    demo_returns(0)[name].rename("ret").rename_axis("date").reset_index().to_csv(path, index=False)
    return path


def test_verify_returns_cli_and_recheck(tmp_path: Path) -> None:
    path = _returns_file(tmp_path, "too_good")
    out = tmp_path / "cert.json"
    code = verify_cmd.main(["--returns", str(path), "--n-strategies", "3", "--out", str(out), "--format", "json"])
    cert = json.loads(out.read_text(encoding="utf-8"))
    assert code == 1 and cert["verdict"] == "NEEDS_MORE_EVIDENCE"
    assert cert["checks"][0]["id"] == "returns_only_scope"
    assert verify_cmd.main(["--returns", str(path), "--recheck", str(out)]) == 0
    assert verify_cmd.main(["--demo-returns"]) == 0


def test_mcp_verify_returns_and_tool_count(tmp_path: Path) -> None:
    report = tools.verify_returns(str(_returns_file(tmp_path, "smoothed")))
    assert {c["id"]: c["status"] for c in report["checks"]}["return_smoothing"] == "warn"
    assert len(tools.TOOLS) == 22


def test_verify_events_cli(tmp_path: Path) -> None:
    n = 400
    stamps = pd.date_range("2022-01-01", periods=n, freq="D")
    close = 100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.01, n)))
    pd.DataFrame({"timestamp": stamps, "open": close, "high": close * 1.01, "low": close * 0.99, "close": close}).to_csv(
        tmp_path / "data.csv", index=False)
    pd.DataFrame({"published_at": stamps[::10], "event_time": stamps[::10] - pd.Timedelta(days=2), "x": 1.0}).to_csv(
        tmp_path / "ev.csv", index=False)
    (tmp_path / "s.py").write_text("def signal(df):\n    return df['ev_x'].fillna(0.0)\n", encoding="utf-8")
    out = tmp_path / "c.json"
    verify_cmd.main(["--ohlcv", str(tmp_path / "data.csv"), "--strategy", str(tmp_path / "s.py"), "--events",
                     str(tmp_path / "ev.csv"), "--events-delay", "3600", "--out", str(out), "--min-trades", "1"])
    cert = json.loads(out.read_text(encoding="utf-8"))
    assert {"events_quality", "pit_events"} <= {c["id"] for c in cert["checks"]}
    assert cert["reproducibility"]["settings"]["events_delay"] == 3600.0
    code = verify_cmd.main(["--ohlcv", str(tmp_path / "data.csv"), "--strategy", str(tmp_path / "s.py"), "--events",
                            str(tmp_path / "ev.csv"), "--recheck", str(out)])
    assert code == 0


def test_alpha_families_with_book(tmp_path: Path) -> None:
    prices, real, _ = demo_panel(3, n_symbols=20, n_days=400)
    dates = pd.to_datetime(prices["timestamp"].unique())
    book = pd.DataFrame({"date": dates, "trend": np.random.default_rng(2).normal(0.0004, 0.01, len(dates))})
    book_path = tmp_path / "book.csv"
    book.to_csv(book_path, index=False)
    report = validate_alpha(prices, real, placebos=50, book=str(book_path), n_trials=20)
    ids = {c["id"] for c in report["checks"]}
    assert {"residual_alpha", "hidden_short_volatility", "marginal_sharpe", "hlz_hurdle", "haircut_sharpe", "tail_risk"} <= ids
    assert report["reproducibility"]["settings"]["n_trials"] == 20
    lean = validate_alpha(prices, real, placebos=50, families=False)
    assert "residual_alpha" not in {c["id"] for c in lean["checks"]}
