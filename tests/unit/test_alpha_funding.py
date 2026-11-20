"""Funding on every perpetual leg of a long-short portfolio and the capacity gate on a stated AUM grid."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.alpha import build_panel, demo_panel, recheck_alpha, validate_alpha
from monte_neo.alpha.funding_cost import capacity_grid_row, funding_drag, funding_drag_row, load_funding
from monte_neo.cli.alpha_cmd import main

PRICES, REAL, _NOISE = demo_panel(1, 12, 250)
PANEL = build_panel(PRICES, REAL)


def _funding(bps: float, drop: float = 0.0) -> pd.DataFrame:
    df = PRICES[["timestamp", "symbol"]].copy()
    df["funding_bps"] = bps
    return df.sample(frac=1 - drop, random_state=0) if drop else df


def _rows(**kw):
    rep = validate_alpha(PRICES, REAL, aum=1e6, seed=0, placebos=20, families=False, **kw)
    return {c["id"]: c for c in rep["checks"]}, rep


def test_funding_drag_is_signed_by_leg() -> None:
    w = np.array([[1.0, -1.0]] * 4)
    f = np.full((4, 2), 10.0)
    total, short, cov = funding_drag(w, f)
    assert np.allclose(total, [0, 0, 0, 0]) and np.allclose(short, [0, -1e-3, -1e-3, -1e-3]) and cov == 1.0  # the long pays what the short receives
    only_long, _, _ = funding_drag(np.array([[1.0, 0.0]] * 3), f[:3])
    assert only_long[1] == pytest.approx(1e-3)
    _, _, cov_nan = funding_drag(w, np.where(np.arange(8).reshape(4, 2) % 2 == 0, np.nan, 10.0))
    assert cov_nan == pytest.approx(0.5 * 3 / 3 * 1.0, abs=0.01)  # half of the held positions have no quote


def test_row_skips_without_history_and_fails_when_funding_eats_the_return() -> None:
    assert funding_drag_row(np.ones((50, 1)), np.ones((50, 1)) * 100, pd.bdate_range("2020-01-01", periods=50), None)["status"] == "skip"
    close = (100.0 * np.cumprod(np.full(300, 1.001))).reshape(-1, 1)
    stamps = pd.bdate_range("2020-01-01", periods=300)
    cheap = funding_drag_row(np.ones((300, 1)), close, stamps, np.full((300, 1), 1.0))
    dear = funding_drag_row(np.ones((300, 1)), close, stamps, np.full((300, 1), 30.0))
    assert cheap["status"] == "pass" and dear["status"] == "fail" and dear["details"]["net_annual_return"] < 0
    thin = funding_drag_row(np.ones((300, 1)), close, stamps, np.where(np.arange(300).reshape(-1, 1) < 100, 1.0, np.nan))
    assert thin["status"] == "warn" and "covers only" in thin["summary"]


def test_load_funding_alignment_and_input_errors() -> None:
    f = load_funding(_funding(2.0), PANEL)
    assert f.shape == PANEL.close.shape and np.nanmin(f) == 2.0
    gap = load_funding(_funding(2.0, drop=0.3), PANEL)
    assert np.isnan(gap).any()
    with pytest.raises(ValueError, match="not in the prices"):
        load_funding(_funding(2.0).query("symbol == 'S00'").assign(symbol="ZZZ"), PANEL)
    with pytest.raises(ValueError, match="duplicate"):
        load_funding(pd.concat([_funding(2.0), _funding(2.0)]), PANEL)


def test_validate_alpha_adds_funding_and_capacity_rows_and_rechecks() -> None:
    by, rep = _rows(funding=_funding(1.0), aum_grid=[250_000, 500_000, 5_000_000], min_capacity=500_000)
    assert by["funding_drag"]["details"]["coverage"] == 1.0 and by["capacity_grid"]["status"] in ("pass", "fail")
    assert [p["aum"] for p in by["capacity_grid"]["details"]["grid"]] == [250_000.0, 500_000.0, 5_000_000.0]
    assert by["capacity_grid"]["details"]["gate_aum"] == 500_000.0 and by["capacity_grid"]["details"]["with_funding"] is True
    again = recheck_alpha(rep, PRICES, REAL, funding=_funding(1.0))
    assert again["reproduced"] is True


def test_default_report_is_unchanged_when_the_new_inputs_are_not_given() -> None:
    by, rep = _rows()
    assert "funding_drag" not in by and "capacity_grid" not in by
    assert set(rep["reproducibility"]["settings"]) .isdisjoint({"funding", "aum_grid", "min_capacity"})


def test_capacity_gate_passes_small_and_fails_large() -> None:
    kw = {"weights": np.where(np.isfinite(PANEL.scores), np.sign(PANEL.scores - np.nanmedian(PANEL.scores, axis=1, keepdims=True)), 0.0) / 6,
          "close": PANEL.close, "volume": PANEL.volume, "timestamps": PANEL.dates}
    small = capacity_grid_row(aum_grid=[1e4], min_capacity=None, **kw)
    huge = capacity_grid_row(aum_grid=[1e4, 1e12], min_capacity=1e12, **kw)
    assert small["details"]["gate_aum"] == 1e4 and huge["details"]["gate_aum"] == 1e12
    assert huge["details"]["grid"][-1]["net_annual_return"] < small["details"]["grid"][0]["net_annual_return"]
    assert huge["status"] == "fail"


def test_capacity_grid_edge_cases() -> None:
    kw = {"weights": np.ones((60, 2)), "close": np.full((60, 2), 10.0), "timestamps": pd.bdate_range("2020-01-01", periods=60)}
    assert capacity_grid_row(volume=np.ones((60, 2)), aum_grid=None, min_capacity=None, **kw)["status"] == "skip"
    assert capacity_grid_row(volume=None, aum_grid=[1e5], min_capacity=None, **kw)["details"]["reason"] == "no_volume"
    with pytest.raises(ValueError, match="positive"):
        capacity_grid_row(volume=np.ones((60, 2)), aum_grid=[0.0, 1e5], min_capacity=None, **kw)


def test_cli_flags(tmp_path, capsys) -> None:
    PRICES.to_csv(tmp_path / "p.csv", index=False)
    REAL.to_csv(tmp_path / "s.csv", index=False)
    _funding(1.0).to_csv(tmp_path / "f.csv", index=False)
    code = main(["--ohlcv", str(tmp_path / "p.csv"), "--scores", str(tmp_path / "s.csv"), "--signal-only", "--funding", str(tmp_path / "f.csv"),
                 "--aum-grid", "250000,5000000", "--min-capacity", "250000", "--format", "json"])
    out = capsys.readouterr().out
    assert code in (0, 1) and '"funding_drag"' in out and '"capacity_grid"' in out
