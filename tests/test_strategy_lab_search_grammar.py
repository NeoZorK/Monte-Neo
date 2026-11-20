"""Strategy Lab search grammar: validation data stays unreachable, batch 1 stays byte-identical (needs the local discovery panel)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "strategy_lab"))
sys.path.insert(0, str(ROOT / "examples" / "strategies" / "_common"))
screen = pytest.importorskip("screen")


def test_guard_rejects_validation_dates():
    idx = pd.to_datetime(["2020-12-31", "2021-01-01"])
    df = pd.DataFrame({"BTCUSDT": [1.0, 2.0]}, index=idx)
    with pytest.raises(RuntimeError):
        screen.assert_disc(df, df)
    screen.assert_disc(df.iloc[:1], df.iloc[:1])


def test_loader_cuts_at_val_start():
    x = screen.lc.load_series("spot", "BTCUSDT", screen.lc.VAL_START)
    if x is None:
        pytest.skip("no local data")
    assert x["timestamp"].max() < screen.lc.VAL_START


def test_variants_unique_and_within_cap():
    v = screen.variants()
    assert len({screen.vid(s) for s in v}) == len(v) <= screen.MAX_VARIANTS


def test_batch1_scores_byte_identical():
    import check_batch1_invariance as ci

    if not (ci.BASE.exists() and (screen.lc.WORK / "screen_panel_disc.pkl").exists()):
        pytest.skip("no local panel")
    assert ci.compute() == __import__("json").loads(ci.BASE.read_text())
