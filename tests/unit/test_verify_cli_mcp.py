"""Unit tests for ``monte-neo verify`` and the MCP adapter."""

from __future__ import annotations

import json
import sys
import types

import numpy as np
import pytest
from rich.console import Console

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.cli import app, verify_cmd
from monte_neo.mcp import server as mcp_server
from monte_neo.mcp import tools

LEAKY = "import numpy as np\n\ndef signal(df):\n    return np.sign(df['close'].shift(-1) - df['close'])\n"


@pytest.fixture(scope="module")
def files(tmp_path_factory) -> dict[str, str]:
    root = tmp_path_factory.mktemp("verify")
    df = synthetic_ohlcv(800, seed=9)
    ohlcv = root / "ohlcv.csv"
    df.to_csv(ohlcv, index=False)
    long_flat = root / "lf.npy"
    np.save(long_flat, (df["close"] > df["close"].rolling(20).mean()).astype(int).to_numpy())
    long_short = root / "ls.npy"
    np.save(long_short, np.where(np.arange(len(df)) % 40 < 20, 1, -1))
    strat = root / "leaky.py"
    strat.write_text(LEAKY)
    return {"ohlcv": str(ohlcv), "lf": str(long_flat), "ls": str(long_short), "strategy": str(strat), "root": str(root)}


def _run(argv: list[str]) -> tuple[int, str]:
    console = Console(record=True, width=200)
    code = verify_cmd.run(verify_cmd.build_parser().parse_args(argv), console)
    return code, console.export_text()


def test_cli_schema_and_usage() -> None:
    code, text = _run(["--schema"])
    assert code == 0 and "strategy-verdict/1" in text
    code, text = _run(["--ohlcv", "x.csv"])
    assert code == 3 and "needs" in text


def test_cli_strategy_reject_writes_certificate(files) -> None:
    out = f"{files['root']}/cert.json"
    code, text = _run(["--ohlcv", files["ohlcv"], "--strategy", files["strategy"], "--out", out])
    assert code == 2 and "REJECT" in text and "→" in text
    assert json.loads(open(out).read())["verdict"] == "REJECT"


def test_cli_signals_json_and_side_modes(files) -> None:
    code, text = _run(["--ohlcv", files["ohlcv"], "--signals", files["lf"], "--format", "json", "--n-trials", "2"])
    assert code in verify_cmd.EXIT_CODES.values()
    assert '"schema": "strategy-verdict/1"' in text and '"long_flat"' in text
    _, text = _run(["--ohlcv", files["ohlcv"], "--signals", files["ls"], "--format", "json"])
    assert '"long_short"' in text
    _, text = _run(["--ohlcv", files["ohlcv"], "--signals", files["ls"], "--side-mode", "long_flat", "--format", "json"])
    assert '"long_flat"' in text


def test_cli_text_without_metrics_and_errors(files, tmp_path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("open,high,low,close\n" + "\n".join("1,0.5,1,1" for _ in range(100)))
    code, text = _run(["--ohlcv", str(bad), "--signals", files["lf"].replace("lf", "missing")])
    assert code == 3 and "verify failed" in text
    np.save(tmp_path / "s.npy", np.ones(100))
    code, text = _run(["--ohlcv", str(bad), "--signals", str(tmp_path / "s.npy")])
    assert code == 2 and "data_integrity" in text and "return" not in text


def test_cli_main_and_app_dispatch(files, monkeypatch) -> None:
    monkeypatch.setattr(verify_cmd, "run", lambda args, console=None: 7)
    assert verify_cmd.main(["--schema"]) == 7
    monkeypatch.setattr(sys, "argv", ["monte-neo-verify", "--schema"])
    assert verify_cmd.main() == 7
    monkeypatch.setattr(sys, "argv", ["monte-neo", "verify", "--schema"])
    assert app.main() == 7


def test_mcp_tools(files) -> None:
    assert "error" in tools.verify_strategy(files["ohlcv"])
    rep = tools.verify_strategy(files["ohlcv"], strategy_path=files["strategy"])
    assert rep["verdict"] == "REJECT"
    assert all("details" not in c for c in rep["checks"] if c["status"] not in ("fail", "warn"))
    full = tools.verify_strategy(files["ohlcv"], signals_path=files["lf"], compact=False, n_trials=4)
    assert all("details" in c for c in full["checks"])
    probe = tools.probe_lookahead(files["ohlcv"], files["strategy"])
    assert probe["leak_detected"] is True
    assert "error" in tools.cost_stress(files["ohlcv"])
    assert "breakeven" in tools.cost_stress(files["ohlcv"], strategy_path=files["strategy"])
    assert "delay" in tools.cost_stress(files["ohlcv"], signals_path=files["ls"])
    assert tools.verdict_schema()["title"] == "strategy-verdict/1"
    manifest = tools.verifier_manifest()
    assert "REJECT" in manifest["verdicts"] and "deflated_sharpe" in manifest["checks"]
    json.dumps(manifest)


def test_mcp_server_registers_tools(monkeypatch) -> None:
    registered: list[str] = []

    class Fake:
        def __init__(self, name: str, instructions: str) -> None:
            self.name = name

        def tool(self):
            def deco(fn):
                registered.append(fn.__name__)
                return fn

            return deco

        def run(self, transport: str) -> None:
            registered.append(f"run:{transport}")

    monkeypatch.setattr(mcp_server, "_server_class", lambda: Fake)
    assert mcp_server.main([]) == 0
    assert registered[-1] == "run:stdio"
    assert set(registered[:-1]) == {fn.__name__ for fn in tools.TOOLS}
    monkeypatch.setattr(sys, "argv", ["monte-neo-mcp", "--transport", "streamable-http"])
    assert mcp_server.main() == 0 and registered[-1] == "run:streamable-http"


def test_mcp_server_class_fallbacks(monkeypatch) -> None:
    pytest.importorskip("mcp")
    real = mcp_server._server_class()
    assert real.__name__ in ("MCPServer", "FastMCP")
    assert mcp_server.build_server() is not None
    legacy = types.ModuleType("mcp.server.fastmcp")
    legacy.FastMCP = type("FastMCP", (), {})
    monkeypatch.setitem(sys.modules, "mcp.server.mcpserver", None)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", legacy)
    assert mcp_server._server_class() is legacy.FastMCP
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", None)
    with pytest.raises(SystemExit, match="monte-neo\\[mcp\\]"):
        mcp_server._server_class()
