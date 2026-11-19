from __future__ import annotations

import pytest

from monte_neo._paths import strategy_file


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("s.py", "s.py"),
        ("s.py:signal", "s.py"),
        ("C:\\Users\\a\\s.py", "C:\\Users\\a\\s.py"),
        ("C:\\Users\\a\\s.py:signal", "C:\\Users\\a\\s.py"),
        ("/tmp/s.py:pnl", "/tmp/s.py"),
        ("C:", "C:"),
    ],
)
def test_strategy_file_keeps_windows_drive_letters(spec: str, expected: str) -> None:
    assert strategy_file(spec) == expected
