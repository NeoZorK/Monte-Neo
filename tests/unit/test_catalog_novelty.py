"""Novelty to a catalog: low correlation with every strategy and a real lift of the catalog book's Sharpe."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.catalog.novelty import novelty
from monte_neo.cli import catalog_cmd

IDX = pd.date_range("2020-01-01", periods=1500, freq="D", tz="UTC")


def _cat(rng: np.random.Generator) -> pd.DataFrame:
    common = rng.normal(0, 0.01, len(IDX))
    return pd.DataFrame({f"s{i}": 0.0003 + 0.7 * common + rng.normal(0, 0.007, len(IDX)) for i in range(4)}, index=IDX)


def test_an_independent_edge_is_novel_and_a_copy_is_not(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rng = np.random.default_rng(0)
    cat = _cat(rng)
    new = pd.Series(0.0008 + rng.normal(0, 0.01, len(IDX)), index=IDX)
    res = novelty(new, cat)
    assert res["novel"] and abs(res["max_abs_corr"]) < 0.3
    copy = cat["s2"] + rng.normal(0, 0.002, len(IDX))
    bad = novelty(copy, cat)
    assert not bad["novel"] and bad["closest"] in cat.columns and any("correlation" in w for w in bad["why_not"])
    new.to_frame("r").to_csv(tmp_path / "r.csv")
    cat.to_csv(tmp_path / "c.csv")
    assert catalog_cmd.main(["novelty", "--returns", str(tmp_path / "r.csv"), "--catalog", str(tmp_path / "c.csv")]) == 0
    assert capsys.readouterr().out.startswith("NOVEL")
    with pytest.raises(ValueError):
        novelty(new, cat.iloc[:, :0])
