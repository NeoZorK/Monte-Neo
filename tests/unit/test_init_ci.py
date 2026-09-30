"""``monte-neo init-ci``: the generated workflow is valid YAML that only uses inputs the action declares."""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
import yaml
from rich.console import Console

from monte_neo.cli.entry import main as entry_main
from monte_neo.cli.init_ci_cmd import build_parser, find_ohlcv, find_strategy, render_workflow, run

ROOT = Path(__file__).parents[2]
ACTION_INPUTS = set(yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))["inputs"])


def _run(argv: list[str], root: Path) -> tuple[int, str]:
    buf = io.StringIO()
    code = run(build_parser().parse_args(argv), Console(file=buf, width=200), root)
    return code, buf.getvalue()


def _project(tmp_path: Path) -> Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "btc.csv").write_text("timestamp,open,high,low,close\n")
    (tmp_path / "strategies").mkdir()
    (tmp_path / "strategies" / "momentum.py").write_text("def signal(df):\n    return df['close'] * 0\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def signal(df):\n    return 0\n")  # tests are not strategies
    return tmp_path


def test_a_typical_project_is_detected_and_the_workflow_is_valid(tmp_path: Path) -> None:
    root = _project(tmp_path)
    code, out = _run(["--n-trials", "12"], root)
    assert code == 0 and "strategies/momentum.py" in out and "data/btc.csv" in out
    doc = yaml.safe_load((root / ".github/workflows/monte-neo.yml").read_text(encoding="utf-8"))
    step = doc["jobs"]["verify"]["steps"][1]
    assert step["uses"].startswith("NeoZorK/Monte-Neo@v")
    assert step["with"]["strategy"] == "strategies/momentum.py" and step["with"]["ohlcv"] == "data/btc.csv"
    assert step["with"]["n-trials"] == "12" and set(step["with"]) <= ACTION_INPUTS
    assert doc["permissions"] == {"contents": "read", "pull-requests": "write"}
    assert re.fullmatch(r"actions/checkout@[0-9a-f]{40}", doc["jobs"]["verify"]["steps"][0]["uses"]), "checkout is pinned"


def test_every_option_uses_a_declared_input() -> None:
    text = render_workflow(
        ohlcv="d.csv", strategy="s.py", version="v0.49.0", n_trials=3, fail_on="NEEDS_MORE_EVIDENCE", isolate=True, sign=True
    )
    step = yaml.safe_load(text)["jobs"]["verify"]["steps"][1]["with"]
    assert set(step) <= ACTION_INPUTS
    assert step["fail-on"] == "NEEDS_MORE_EVIDENCE" and step["isolate"] == "true"
    assert step["signing-key"] == "${{ secrets.MONTE_NEO_SIGNING_KEY }}"
    assert "n-trials" not in yaml.safe_load(render_workflow(ohlcv="d", strategy="s", version="v1"))["jobs"]["verify"]["steps"][1]["with"]


def test_it_never_overwrites_without_force(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert _run([], root)[0] == 0
    code, out = _run([], root)
    assert code == 3 and "already exists" in out
    assert _run(["--force", "--out", ".github/workflows/monte-neo.yml"], root)[0] == 0


def test_ambiguous_projects_get_placeholders_and_a_note(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def signal(df):\n    return 0\n")
    (tmp_path / "b.py").write_text("def signal(df):\n    return 1\n")
    (tmp_path / "x.csv").write_text("c\n")
    (tmp_path / "y.csv").write_text("c\n")
    assert find_strategy(tmp_path)[0] is None and find_ohlcv(tmp_path)[0] is None
    code, out = _run([], tmp_path)
    assert code == 0 and "several files define signal()" in out and "several price tables" in out
    doc = yaml.safe_load((tmp_path / ".github/workflows/monte-neo.yml").read_text(encoding="utf-8"))
    assert doc["jobs"]["verify"]["steps"][1]["with"]["strategy"] == "strategy.py"


def test_strategy_py_wins_when_several_files_define_a_signal(tmp_path: Path) -> None:
    (tmp_path / "strategy.py").write_text("def signal(df):\n    return 0\n")
    (tmp_path / "other.py").write_text("def signal(df):\n    return 1\n")
    assert find_strategy(tmp_path)[0] == "strategy.py"


def test_tool_folders_are_not_searched(tmp_path: Path) -> None:
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("def signal(df):\n    return 0\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "d.csv").write_text("c\n")
    assert find_strategy(tmp_path)[0] is None and find_ohlcv(tmp_path)[0] is None


def test_print_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _project(tmp_path)
    assert _run(["--print"], root)[0] == 0
    assert "NeoZorK/Monte-Neo@" in capsys.readouterr().out
    assert not (root / ".github").exists()


def test_the_command_is_reachable_and_bad_options_exit_3(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["monte-neo", "init-ci", "--fail-on", "NOPE"])
    assert entry_main() == 3
    monkeypatch.setattr("sys.argv", ["monte-neo", "--help"])
    assert entry_main() == 0 and "init-ci" in capsys.readouterr().out
