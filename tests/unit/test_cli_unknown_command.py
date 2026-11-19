from __future__ import annotations

import sys

from monte_neo.cli import entry


def test_unknown_command_is_named_with_a_suggestion(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["monte-neo", "verfy"])
    assert entry.main() == 2
    err = capsys.readouterr().err
    assert "unknown command 'verfy'" in err and "monte-neo verify" in err


def test_unknown_command_without_close_match(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["monte-neo", "zzzzzz"])
    assert entry.main() == 2
    assert "Did you mean" not in capsys.readouterr().err
