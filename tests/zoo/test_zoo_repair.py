"""Zoo A16 (repair): repairing a leaking strategy on a market without an edge must never report REPAIRED.

``ZOO_LEVEL=lite`` (CI) runs six classic leaks; ``full`` (nightly) runs every trap of the Trap Suite that is not an honest
control. A false REPAIRED would mean the repair found a new curve fit instead of removing a defect.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.repair import repair_strategy

TRAPS = Path(__file__).parents[1] / "traps" / "strategies"
LITE = ["lookahead_shift", "bfill_leak", "centered_window", "global_zscore", "gradient_leak", "fft_denoise"]


def _honest() -> set[str]:
    """The honest controls, read from the Trap Suite itself (one list, one place)."""
    tree = ast.parse((Path(__file__).parents[1] / "traps" / "test_trap_suite.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "HONEST" for t in node.targets):
            return set(ast.literal_eval(node.value))
    raise RuntimeError("HONEST not found in tests/traps/test_trap_suite.py")


HONEST = _honest()
NAMES = LITE if os.environ.get("ZOO_LEVEL", "lite") != "full" else sorted(
    p.stem for p in TRAPS.glob("*.py") if p.stem not in HONEST and not p.stem.startswith("_"))


@pytest.fixture(scope="module")
def random_walk():
    return synthetic_ohlcv(1500, seed=17)


@pytest.mark.parametrize("name", NAMES)
def test_repair_never_invents_an_edge(name: str, random_walk, tmp_path: Path) -> None:
    path = TRAPS / f"{name}.py"
    before = path.read_bytes()
    try:
        rep = repair_strategy(random_walk, str(path), out_dir=tmp_path / name, budget=8)
    except (ValueError, KeyError, AttributeError) as exc:  # a trap that needs other data columns
        pytest.skip(f"{name}: {exc}")
    assert rep["outcome"] != "REPAIRED", (name, rep.get("chosen"), rep.get("lockbox"))
    assert path.read_bytes() == before  # the original is never touched
