"""``verify --suggest-fix`` and the MCP tool ``suggest_fix``."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from rich.console import Console

from monte_neo.cli.verify_cmd import _run_suggest_fix
from monte_neo.mcp.tools import TOOLS, suggest_fix

LEAK = 'def signal(df):\n    return (df["close"].shift(-3) > df["close"]).astype(int).to_numpy()\n'


def _run(path: Path) -> tuple[int, str]:
    buf = io.StringIO()
    code = _run_suggest_fix(str(path), Console(file=buf, width=200))
    return code, buf.getvalue()


def test_the_cli_prints_the_rewrite_and_a_diff(tmp_path: Path) -> None:
    f = tmp_path / "s.py"
    f.write_text(LEAK)
    code, out = _run(f)
    assert code == 1 and "negative_shift" in out and "-    return" in out and "shift(3)" in out and "verify the patched file" in out
    assert f.read_text() == LEAK, "nothing is written"


def test_clean_unreadable_and_broken_files(tmp_path: Path) -> None:
    clean = tmp_path / "c.py"
    clean.write_text("def signal(df):\n    return df['close'].rolling(5).mean()\n")
    assert _run(clean) == (0, f"{clean}: no rewrite suggested\n")
    assert _run(tmp_path / "missing.py")[0] == 3
    broken = tmp_path / "b.py"
    broken.write_text("def (:")
    assert _run(broken)[0] == 3


def test_the_mcp_tool_returns_the_patch(tmp_path: Path) -> None:
    f = tmp_path / "s.py"
    f.write_text(LEAK)
    result = suggest_fix(str(f))
    assert suggest_fix in TOOLS and result["changes"][0]["rule"] == "negative_shift" and "shift(3)" in result["patched"]
    with pytest.raises(FileNotFoundError):
        suggest_fix(str(tmp_path / "nope.py"))
