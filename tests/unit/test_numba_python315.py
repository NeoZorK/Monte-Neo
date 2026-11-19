"""Python 3.15 must never resolve to a Numba that cannot be installed there."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_floors_numba_for_python_315():
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    assert any(d.startswith("numba>=0.68") and "python_version >= '3.15'" in d for d in deps)


def test_lock_pins_a_numba_with_python_315_support():
    text = (ROOT / "uv.lock").read_text(encoding="utf-8")
    versions = re.findall(r'\[\[package\]\]\nname = "numba"\nversion = "(\d+)\.(\d+)\.', text)
    assert versions, "numba missing from uv.lock"
    assert all((int(a), int(b)) >= (0, 68) for a, b in versions)
