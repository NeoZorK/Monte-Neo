"""Regression tests for the v0.57.1 fixes found by the post-release check of v0.57.0."""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_data_extra_brings_a_parquet_engine():
    extras = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["optional-dependencies"]
    assert any(r.startswith("pyarrow") for r in extras["data"])


def test_asset_class_accepts_codes_and_common_names_and_refuses_unknown():
    from monte_neo.catalog.classify import _asset_classes, asset_code

    assert asset_code("CRY") == "CRY"
    assert asset_code("crypto") == "CRY"
    assert asset_code("Equities") == "EQ"
    assert _asset_classes({"instruments": [{"symbol": "BTCUSDT", "asset_class": "CRYPTO"}]}) == ["CRY"]
    with pytest.raises(ValueError, match="unknown asset_class"):
        asset_code("PLANETS")


def test_compat_reads_a_common_asset_name_as_its_code():
    from monte_neo.catalog.compat import requirements

    req = requirements({"instruments": [{"symbol": "BTCUSDT", "type": "spot", "asset_class": "CRYPTO"}]})
    assert req["asset_classes"] == ["CRY"]


def test_breadth_keeps_names_listed_later():
    from monte_neo.research.breadth import _names_text, effective_breadth

    rng = np.random.default_rng(0)
    x = rng.normal(size=(400, 4))
    x[:150, 2] = np.nan  # a coin listed later
    x[:300, 3] = np.nan
    br = effective_breadth(pd.DataFrame(x))
    assert br["n_names"] == 4
    assert 1.0 <= br["n_eff"] <= 4.0
    assert "4 names act like" in _names_text(br)
    assert "counted as 1 bet" in _names_text({"n_names": 0, "n_eff": 1.0})


def test_deploy_keys_without_terminal_fails_fast(monkeypatch, capsys):
    from monte_neo.cli import deploy_cmd
    from monte_neo.deploy import keys

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr(keys, "candidates", lambda: pytest.fail("must not scan the disk without consent"))
    rc = deploy_cmd._keys(argparse.Namespace(venue="binance_spot", status=False, list=False, yes=False))
    assert rc == 2
    assert "no terminal" in capsys.readouterr().err


def test_hall_build_resolves_readme_and_docs_next_to_root(tmp_path, monkeypatch):
    from monte_neo.cli import hall_cmd

    seen = {}

    class Res:
        errors: list[str] = []
        files: list[Path] = []

    def fake_build(root, readme, docs, month):
        seen.update(root=root, readme=readme, docs=docs)
        return Res()

    monkeypatch.setattr(hall_cmd, "build", fake_build)
    monkeypatch.setattr(hall_cmd, "write", lambda res: [])
    repo = tmp_path / "repo"
    (repo / "hall_of_fame").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace(root=str(repo / "hall_of_fame"), readme=None, docs=None, guide=None, month="2026-11", check=False)
    assert hall_cmd._build(args) == 0
    assert seen["readme"] == repo.resolve() / "README.md"
    assert seen["docs"] == repo.resolve() / "docs" / "hall-of-fame.md"
