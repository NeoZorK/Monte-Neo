"""Panel loading and alignment for the alpha validator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.alpha import build_panel, demo_panel
from monte_neo.alpha.panel import data_sha256


def _tables(n_days: int = 30, n_sym: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2021-01-01", periods=n_days)
    syms = [f"A{i}" for i in range(n_sym)]
    rng = np.random.default_rng(0)
    px = pd.DataFrame({"timestamp": np.repeat(dates, n_sym), "ticker": np.tile(syms, n_days), "close": 100 + rng.random(n_days * n_sym)})
    sc = pd.DataFrame({"date": np.repeat(dates, n_sym), "symbol": np.tile(syms, n_days), "score": rng.standard_normal(n_days * n_sym)})
    return px, sc


def test_alignment_and_forward_returns() -> None:
    px, sc = _tables()
    panel = build_panel(px, sc)
    assert panel.close.shape == panel.scores.shape == (30, 5)
    fwd = panel.forward_returns(3)
    assert np.isnan(fwd[-3:]).all()
    assert np.allclose(fwd[0], panel.close[3] / panel.close[0] - 1)


def test_missing_stay_nan() -> None:
    px, sc = _tables()
    sc = sc.drop(sc.index[7])
    panel = build_panel(px, sc)
    assert np.isnan(panel.scores).sum() == 1


def test_csv_roundtrip(tmp_path) -> None:
    px, sc = _tables()
    px.to_csv(tmp_path / "p.csv", index=False)
    sc.to_csv(tmp_path / "s.csv", index=False)
    panel = build_panel(tmp_path / "p.csv", tmp_path / "s.csv")
    assert panel.symbols == ["A0", "A1", "A2", "A3", "A4"]
    assert len(data_sha256(tmp_path / "p.csv")) == 64


def test_duplicates_rejected() -> None:
    px, sc = _tables()
    with pytest.raises(ValueError, match="duplicate"):
        build_panel(px, pd.concat([sc, sc.iloc[:1]]))


def test_unknown_symbol_rejected() -> None:
    px, sc = _tables()
    sc.loc[0, "symbol"] = "ZZZ"
    with pytest.raises(ValueError, match="missing from prices"):
        build_panel(px, sc)


def test_score_after_last_price_rejected() -> None:
    px, sc = _tables()
    late = sc.iloc[:1].copy()
    late["date"] = pd.Timestamp("2030-01-01")
    with pytest.raises(ValueError, match="after the last price"):
        build_panel(px, pd.concat([sc, late]))


def test_too_few_symbols_rejected() -> None:
    px, sc = _tables(n_sym=2)
    with pytest.raises(ValueError, match="at least 3 symbols"):
        build_panel(px, sc)


def test_too_few_scored_symbols_per_date_rejected() -> None:
    px, sc = _tables()
    sc = sc[sc["symbol"].isin(["A0", "A1"])]
    with pytest.raises(ValueError, match="fewer than 3"):
        build_panel(px, sc)


def test_missing_column_rejected() -> None:
    px, sc = _tables()
    with pytest.raises(ValueError, match="score"):
        build_panel(px, sc.drop(columns="score"))


def test_scores_do_not_depend_on_future_prices() -> None:
    """Prices after t change forward returns (targets) but never the score matrix or earlier closes."""
    prices, real, _ = demo_panel(1, 10, 100)
    base = build_panel(prices, real)
    cut = base.dates[50]
    changed = prices.copy()
    changed.loc[changed["timestamp"] > cut, "close"] *= 1.5
    other = build_panel(changed, real)
    assert np.array_equal(base.scores, other.scores, equal_nan=True)
    assert np.array_equal(base.close[:51], other.close[:51])
    assert np.array_equal(base.forward_returns(1)[:49], other.forward_returns(1)[:49], equal_nan=True)
    assert not np.array_equal(base.forward_returns(1)[50], other.forward_returns(1)[50])
