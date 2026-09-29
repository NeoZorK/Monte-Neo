"""Input robustness: broken bars, unhelpful errors, MCP error reporting, fast entry point."""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli import entry
from monte_neo.mcp import tools
from monte_neo.mcp.server import reporting_errors
from monte_neo.verify import checks as rows
from monte_neo.verify import verify_strategy


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return synthetic_ohlcv(400, seed=4)


@pytest.mark.parametrize(("column", "ref", "factor"), [("close", "high", 1.2), ("open", "low", 0.5)])
def test_open_or_close_outside_the_range_fails(df, column: str, ref: str, factor: float) -> None:
    broken = df.copy()
    broken.loc[100, column] = broken.loc[100, ref] * factor
    report = verify_strategy(broken, signals=np.ones(len(df)))
    row = report["checks"][0]
    assert report["verdict"] == "REJECT" and row["details"]["open_close_outside_range"] == 1
    assert "open/close outside high-low" in row["summary"]


def test_rounding_gaps_are_counted_not_failed() -> None:
    ohlc = {"open": np.array([100.0, 100.0]), "high": np.array([101.0, 101.0]),
            "low": np.array([99.0, 99.0]), "close": np.array([101.05, 100.0])}
    row = rows.data_integrity(ohlc)
    assert row["status"] == "pass" and row["details"]["rounding_outside_range"] == 1


@pytest.mark.parametrize(
    ("fn", "message"),
    [
        (lambda d: None, "returned None"),
        (lambda d: 1, "single value"),
        (lambda d: np.array(["buy"] * len(d)), "positions must be numbers"),
    ],
)
def test_signal_errors_say_what_to_fix(df, fn, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        verify_strategy(df, signal_fn=fn)


def test_universe_rows_without_symbol(df) -> None:
    uni = pd.concat([df.assign(symbol="A"), df.assign(symbol="B")], ignore_index=True)
    uni.loc[3, "symbol"] = None
    with pytest.raises(ValueError, match="1 rows have no symbol"):
        verify_strategy(uni, signals=np.ones(len(uni)))


def test_mcp_errors_reach_the_agent() -> None:
    wrapped = reporting_errors(tools.verify_strategy)
    out = wrapped("/no/such/file.csv", strategy_path="x.py")
    assert out["tool"] == "verify_strategy" and out["error"].startswith("FileNotFoundError")
    assert wrapped.__wrapped__ is tools.verify_strategy  # the SDK reads the signature through it
    assert reporting_errors(lambda: {"ok": 1})() == {"ok": 1}


def test_entry_point_dispatch(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["monte-neo", "--version"])
    assert entry.main() == 0 and capsys.readouterr().out.startswith("monte-neo v")
    calls = []
    import monte_neo.cli.bench_cmd as bench_cmd
    import monte_neo.cli.verify_cmd as verify_cmd
    import monte_neo.mcp.server as server
    from monte_neo.cli import app

    monkeypatch.setattr(verify_cmd, "main", lambda argv: calls.append(("verify", argv)) or 0)
    monkeypatch.setattr(bench_cmd, "main", lambda argv: calls.append(("bench", argv)) or 0)
    monkeypatch.setattr(server, "main", lambda argv: calls.append(("mcp", argv)) or 0)
    monkeypatch.setattr(app, "main", lambda: calls.append(("app", [])) or 0)
    for argv in (["verify", "--schema"], ["bench", "x"], ["mcp"], []):
        monkeypatch.setattr(sys, "argv", ["monte-neo", *argv])
        assert entry.main() == 0
    assert [c[0] for c in calls] == ["verify", "bench", "mcp", "app"]
    assert calls[0][1] == ["--schema"]


def test_cli_package_is_lazy() -> None:
    code = "import sys, monte_neo.cli.verify_cmd; print('monte_neo.cli.menu' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
    import monte_neo.cli as cli

    assert cli.ProgressTracker.__name__ == "ProgressTracker"
    with pytest.raises(AttributeError):
        cli.nothing_here  # noqa: B018
