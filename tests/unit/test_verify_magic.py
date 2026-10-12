"""The ``%%verify`` cell magic, driven by a fake ipython object (IPython is not needed)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from monte_neo.backtest import synthetic_ohlcv
from monte_neo.verify import magic
from monte_neo.verify.notebook import Certificate

CELL = "import numpy as np\n\ndef signal(df):\n    fast = df['close'].rolling(10).mean()\n    slow = df['close'].rolling(40).mean()\n    return np.where(fast > slow, 1, 0)\n"


class FakeIPython:
    def __init__(self) -> None:
        self.registered: dict[str, Any] = {}

    def register_magic_function(self, func: Any, magic_kind: str = "line", magic_name: str | None = None) -> None:
        self.registered[f"{magic_kind}:{magic_name}"] = func


def test_extension_registers_cell_magic() -> None:
    ip = FakeIPython()
    magic.load_ipython_extension(ip)
    assert ip.registered == {"cell:verify": magic.verify_cell}


def test_cell_is_verified_and_returns_certificate(tmp_path: Path) -> None:
    csv = tmp_path / "bars.csv"
    synthetic_ohlcv(1500, seed=3).to_csv(csv, index=False)
    out = magic.verify_cell(f"--ohlcv {csv} --n-trials 5 --commission-bps 2 --slippage-bps 1", CELL)
    assert isinstance(out, Certificate)
    assert isinstance(out["verdict"], str)
    assert "<iframe" in out._repr_html_()


def test_bad_arguments_and_empty_cell(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="usage"):
        magic.verify_cell("--bogus", CELL)
    with pytest.raises(ValueError, match="empty"):
        magic.verify_cell("--ohlcv x.csv", "  \n")


def test_module_imports_without_ipython() -> None:
    import sys

    assert "IPython" not in sys.modules or sys.modules["IPython"] is not None
    assert callable(magic.load_ipython_extension)
