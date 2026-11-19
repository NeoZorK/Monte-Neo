"""Strategy Lab: the signals are causal, the grids are declared, and the holdout gate refuses an unfrozen candidate."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "strategy_lab"))
import labcore as lc  # noqa: E402
import labstages  # noqa: E402


def _bars(n: int = 700) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    close = 100 * np.exp(np.cumsum(0.02 * rng.standard_normal(n)))
    return pd.DataFrame({"timestamp": pd.date_range("2020-01-01", periods=n, freq="D"), "open": close, "high": close * 1.01,
                         "low": close * 0.99, "close": close, "volume": 1e6})


def test_ten_ideas_with_cards_and_one_pair() -> None:
    names = lc.names()
    assert len(names) >= 10
    assert sum(bool(lc.load_module(n).META.get("pair")) for n in names) >= 1
    for n in names:
        assert (lc.STRATS / n / "card.md").exists()
        assert "not investment advice" in (lc.STRATS / n / "card.md").read_text().lower()
        assert lc.combos(lc.load_module(n).META["grid"])


@pytest.mark.parametrize("name", [n for n in lc.names() if lc.load_module(n).META["kind"] == "verify"])
def test_signal_does_not_use_the_future(name: str) -> None:
    sig = lc.load_module(name).signal
    df = _bars()
    full = np.asarray(sig(df))
    cut = np.asarray(sig(df.iloc[:500].reset_index(drop=True)))
    np.testing.assert_allclose(full[:500], cut, equal_nan=True)


def test_holdout_refuses_unfrozen_candidate() -> None:
    with pytest.raises(RuntimeError, match="not frozen"):
        labstages.frozen_ok("tsmom_btc")


def test_holdout_stage_end_to_end_on_synthetic_data(tmp_path, monkeypatch) -> None:
    """The whole path (prepare, validation, holdout with the oracle) on random-walk data in a scratch folder."""
    rng = np.random.default_rng(5)
    idx = pd.date_range("2019-01-01", "2026-06-30", freq="D")
    close = 100 * np.exp(np.cumsum(0.02 * rng.standard_normal(len(idx))))
    data = tmp_path / "data"
    data.mkdir()
    pd.DataFrame({"timestamp": idx, "open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": 1e6}).to_parquet(data / "spot_BTCUSDT_1d.parquet")
    for attr, val in (("DATA", data), ("WORK", tmp_path / "work"), ("RES", tmp_path / "res"), ("MNDIR", tmp_path / "work" / "mn"), ("LAB_LEDGER", tmp_path / "work" / "ledger.jsonl")):
        monkeypatch.setattr(lc, attr, val)
    (tmp_path / "res" / "tsmom_btc").mkdir(parents=True)
    labstages.stage_prepare("tsmom_btc")
    (tmp_path / "res" / "tsmom_btc" / "prepare.json").write_text('{"registration": "none"}')
    monkeypatch.setattr(labstages, "frozen_ok", lambda n: {"strategy_sha256": "x", "commit": "c" * 40})
    rec = labstages.stage_holdout("tsmom_btc")
    assert rec["slice"] == "full" and rec["verdict"] and "oracle" in rec
    assert isinstance(rec["passes_all_gates"], bool)
