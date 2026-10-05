"""``monte-neo discover`` and the MCP tool ``discover_indicator``."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli.discover_cmd import main
from monte_neo.mcp.tools import TOOLS, discover_indicator

SMALL = ["--budget", "60", "--null-runs", "3"]


def _csv(tmp_path: Path) -> Path:
    path = tmp_path / "d.csv"
    synthetic_ohlcv(900, seed=3).to_csv(path, index=False)
    return path


def test_the_command_writes_every_file_and_keeps_the_journal_out_of_result_json(tmp_path: Path) -> None:
    out = tmp_path / "o"
    code = main(["--ohlcv", str(_csv(tmp_path)), "--out", str(out), *SMALL])
    assert code in (0, 1)
    for name in ("strategy.py", "result.json", "search.jsonl", "certificate.json", "report.html"):
        assert (out / name).is_file()
    result = json.loads((out / "result.json").read_text())
    assert "journal" not in result and result["search"]["candidates"] > 0
    assert len((out / "search.jsonl").read_text().splitlines()) == result["search"]["candidates"]


def test_bad_input_exits_with_3(tmp_path: Path, capsys) -> None:
    short = tmp_path / "s.csv"
    synthetic_ohlcv(100, seed=1).to_csv(short, index=False)
    assert main(["--ohlcv", str(short), *SMALL]) == 3
    assert "400 bars" in capsys.readouterr().err
    assert main(["--ohlcv", str(tmp_path / "missing.csv")]) == 3


def test_the_mcp_tool_is_listed_and_returns_no_journal(tmp_path: Path) -> None:
    assert discover_indicator in TOOLS
    result = discover_indicator(str(_csv(tmp_path)), budget=60, null_runs=3)
    assert "journal" not in result and "certificate" in result and "found" in result


def test_the_entry_point_dispatches(tmp_path: Path, monkeypatch) -> None:
    from monte_neo.cli import entry

    monkeypatch.setattr(sys, "argv", ["monte-neo", "discover", "--ohlcv", str(tmp_path / "none.csv")])
    assert entry.main() == 3


def test_a_recorded_search_is_reproduced_and_a_changed_journal_is_not(tmp_path: Path, capsys) -> None:
    csv, out = _csv(tmp_path), tmp_path / "o"
    assert main(["--ohlcv", str(csv), "--out", str(out), *SMALL]) in (0, 1)
    capsys.readouterr()
    assert main(["--ohlcv", str(csv), "--recheck", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["reproduced"] is True
    (out / "search.jsonl").write_text("{}\n" + (out / "search.jsonl").read_text())
    assert main(["--ohlcv", str(csv), "--recheck", str(out)]) == 4
    assert json.loads(capsys.readouterr().out)["journal_file"] is False


def test_evolution_adds_counted_children_and_is_deterministic(tmp_path: Path) -> None:
    from monte_neo.discover import Config, discover

    df = synthetic_ohlcv(900, seed=3)
    a = discover(df, Config(budget=60, null_runs=2, evolve=2))
    b = discover(df, Config(budget=60, null_runs=2, evolve=2))
    plain = discover(df, Config(budget=60, null_runs=2))
    assert a["journal_sha256"] == b["journal_sha256"]
    assert a["search"]["candidates"] > plain["search"]["candidates"]
    assert a["search"]["effective_trials"] >= 1 and a["search"]["pbo"] is None or 0.0 <= a["search"]["pbo"] <= 1.0
