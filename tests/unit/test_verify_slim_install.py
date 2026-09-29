"""The base install (no research extras): clear messages when an optional package is missing."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

from monte_neo.cli import entry
from monte_neo.verify.ingest import _read_table


def test_parquet_without_pyarrow_names_the_extra(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def missing(*args: object, **kwargs: object) -> pd.DataFrame:
        raise ImportError("Unable to find a usable engine")

    monkeypatch.setattr(pd, "read_parquet", missing)
    with pytest.raises(ImportError, match=r"monte-neo\[parquet\]"):
        _read_table(tmp_path / "prices.parquet")


def test_research_cli_without_extras_names_the_extra(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["monte-neo"])
    monkeypatch.setitem(sys.modules, "monte_neo.cli.app", None)  # import fails as with questionary missing
    assert entry.main() == 2
    err = capsys.readouterr().err
    assert "monte-neo[research]" in err and "monte-neo verify" in err


def test_base_dependencies_leave_out_research_packages() -> None:
    import tomllib

    project = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    base = " ".join(project["dependencies"])
    for name in ("pyarrow", "questionary", "prompt-toolkit", "python-dotenv", "pybind11", "pyyaml"):
        assert name not in base
        assert any(dep.startswith(name) for dep in project["optional-dependencies"]["research"])
    assert project["optional-dependencies"]["parquet"] == ["pyarrow>=23.0.1"]
