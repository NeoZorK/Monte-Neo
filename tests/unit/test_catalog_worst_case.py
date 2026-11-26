"""Worst-scenario card: measured losses, hedge behaviour and stated shocks."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from monte_neo.catalog import worst_case
from monte_neo.cli import catalog_cmd


def _legs(n: int = 600, seed: int = 3) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    common = rng.normal(0, 0.03, n)
    long_leg = pd.Series(common + rng.normal(0.0004, 0.006, n), index=idx)
    short_leg = pd.Series(common + rng.normal(0.0, 0.006, n), index=idx)
    return long_leg, short_leg


def test_measured_numbers_by_hand() -> None:
    idx = pd.date_range("2024-01-01", periods=40, freq="D", tz="UTC")
    r = pd.Series([0.01] * 40, index=idx)
    r.iloc[10] = -0.2
    m = worst_case.measured(r)
    assert m["worst_bar"] == pytest.approx(-0.2)
    assert m["max_drawdown"] == pytest.approx(-0.2)
    assert m["expected_shortfall_1pct"] == pytest.approx(-0.2)  # one bar in 40 is the worst 1 %
    assert m["longest_drawdown_bars"] >= 1


def test_neutral_book_looks_calm_but_the_card_shows_the_tails() -> None:
    lg, sh = _legs()
    book = 0.5 * lg - 0.5 * sh
    c = worst_case.card(book, (lg, sh))
    assert abs(c["measured"]["max_drawdown"]) < 0.25  # the book itself is calm
    assert c["hedge"]["corr_all"] > 0.8
    assert c["hedge"]["long_alone_worst_21"] < c["measured"]["worst_21"]  # unhedged the leg loses far more
    assert c["headline"]["loss"] <= c["shocks"]["short_squeeze"]["loss"] == pytest.approx(-0.25)
    assert c["counterparty"]["loss"] == -1.0 and "venue_failure" not in c["headline"]["scenario"]
    md = worst_case.markdown(c)
    assert "Counterparty" in md and "not forecasts" in md and "Not investment advice" in md


def test_assumptions_change_the_stated_shocks() -> None:
    lg, sh = _legs()
    c = worst_case.card(0.5 * lg - 0.5 * sh, None, short_weight=0.3, squeeze_jump=1.0, venue_share=0.4, funding_spike_bps_day=10)
    assert c["shocks"]["short_squeeze"]["loss"] == pytest.approx(-0.3)
    assert c["shocks"]["funding_spike"]["loss"] == pytest.approx(-0.3 * 10 / 1e4 * 30)
    assert c["shocks"]["venue_failure"]["loss"] == pytest.approx(-0.4)
    assert c["hedge"] is None and "spread_break" not in c["shocks"]


def test_cli_writes_the_card(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lg, sh = _legs()
    pd.DataFrame({"ret": 0.5 * lg - 0.5 * sh}).to_csv(tmp_path / "r.csv")
    pd.DataFrame({"long": lg, "short": sh}).to_csv(tmp_path / "legs.csv")
    out = tmp_path / "card.md"
    assert catalog_cmd.main(["worst", "--returns", str(tmp_path / "r.csv"), "--legs", str(tmp_path / "legs.csv"), "--out", str(out)]) == 0
    assert out.read_text().startswith("## Worst scenario") and "hedge_stops_working" in capsys.readouterr().out
