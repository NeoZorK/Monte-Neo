"""Point-in-time liquid universe, declared delisting returns and one rebalance phase for the alpha report."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monte_neo.alpha import build_panel, demo_panel, recheck_alpha, validate_alpha
from monte_neo.alpha.universe_tools import (
    apply_rebalance_phase,
    apply_terminal_returns,
    liquid_mask,
    membership_from_mask,
    parse_phase,
    prepare_panel,
)
from monte_neo.cli.alpha_cmd import main

PRICES, REAL, _ = demo_panel(3, 10, 200)


def _panel(prices=PRICES):
    return build_panel(prices, REAL)


def _with_volume() -> pd.DataFrame:
    p = PRICES.copy()
    sym_rank = p["symbol"].str[1:].astype(int)
    p["volume"] = 1000.0 * (1 + sym_rank)  # S09 is the most liquid, S00 the least
    return p


def test_liquid_mask_uses_only_past_bars_and_picks_the_top() -> None:
    panel = _panel(_with_volume())
    m = liquid_mask(panel, 3, lookback=10)
    assert not m[:10].any() and (m[10:].sum(axis=1) == 3).all()
    assert set(np.array(panel.symbols)[m[50]]) == {"S07", "S08", "S09"}
    spike = _with_volume()
    spike.loc[(spike["symbol"] == "S00") & (spike["timestamp"] == spike["timestamp"].unique()[60]), "volume"] = 1e12
    m2 = liquid_mask(_panel(spike), 3, lookback=10)
    assert not m2[60, 0] and m2[61, 0]  # a volume spike counts from the next bar, never on its own date


def test_liquid_mask_input_errors() -> None:
    with pytest.raises(ValueError, match="top_k"):
        liquid_mask(_panel(_with_volume()), 0)
    with pytest.raises(ValueError, match="needs volume"):
        liquid_mask(_panel(PRICES.drop(columns="volume", errors="ignore").assign(volume=np.nan)), 3)


def test_membership_windows_follow_the_mask() -> None:
    panel = _panel(_with_volume())
    m = np.zeros((len(panel.dates), len(panel.symbols)), dtype=bool)
    m[5:9, 0] = True
    m[20:, 0] = True
    rows = membership_from_mask(panel, m)
    assert len(rows) == 2 and rows.iloc[0]["start"] == panel.dates[5] and rows.iloc[0]["end"] == panel.dates[8] and rows.iloc[1]["end"] == panel.dates[-1]


def _delisted():
    p = PRICES[~((PRICES["symbol"] == "S01") & (PRICES["timestamp"] > PRICES["timestamp"].unique()[150]))]
    return build_panel(p, REAL[~((REAL["symbol"] == "S01") & (REAL["timestamp"] > REAL["timestamp"].unique()[150]))])


def test_delisting_return_is_applied_or_flagged() -> None:
    panel = _delisted()
    j = panel.symbols.index("S01")
    last = int(np.flatnonzero(np.isfinite(panel.close[:, j]))[-1])
    new, row = apply_terminal_returns(panel, {"S01": -0.9})
    assert row["status"] == "pass" and new.close[last + 1, j] == pytest.approx(panel.close[last, j] * 0.1)
    assert apply_terminal_returns(panel, {})[1]["status"] == "warn" and apply_terminal_returns(_panel(), {})[1]["status"] == "skip"
    with pytest.raises(ValueError, match="not in the prices"):
        apply_terminal_returns(panel, {"ZZZ": -1.0})
    with pytest.raises(ValueError, match="at least -1.0"):
        apply_terminal_returns(panel, {"S01": -1.5})


def test_rebalance_phase_holds_scores_between_rebalances() -> None:
    panel = _panel()
    held = apply_rebalance_phase(panel, "2/5")
    assert np.isnan(held.scores[:2]).all() and np.array_equal(held.scores[2], panel.scores[2]) and np.array_equal(held.scores[4], panel.scores[2])
    assert np.array_equal(held.scores[7], panel.scores[7])
    assert parse_phase((0, 1)) == (0, 1)
    for bad in ("5/5", "-1/3", "0/0"):
        with pytest.raises(ValueError, match="K/H"):
            parse_phase(bad)


def test_prepare_panel_is_a_no_op_without_inputs() -> None:
    panel = _panel()
    same, rows, mem = prepare_panel(panel, liquid_top=None, liquid_lookback=30, terminal_returns=None, rebalance_phase=None)
    assert same is panel and rows == [] and mem is None


def test_validate_alpha_with_all_inputs_and_recheck() -> None:
    kw = {"liquid_top": 6, "liquid_lookback": 20, "terminal_returns": {}, "rebalance_phase": "1/5"}
    rep = validate_alpha(_with_volume(), REAL, families=True, placebos=20, **kw)
    ids = {c["id"]: c for c in rep["checks"]}
    assert ids["delisting_returns"]["status"] == "skip" and rep["reproducibility"]["settings"]["rebalance_phase"] == "1/5"
    assert recheck_alpha(rep, _with_volume(), REAL)["reproduced"] is True
    plain = validate_alpha(_with_volume(), REAL, families=False, placebos=20)
    assert plain["reproducibility"]["settings"].keys().isdisjoint({"liquid_top", "terminal_returns", "rebalance_phase"})


def test_cli_flags(tmp_path, capsys) -> None:
    _with_volume().to_csv(tmp_path / "p.csv", index=False)
    REAL.to_csv(tmp_path / "s.csv", index=False)
    pd.DataFrame({"symbol": ["S01"], "return": [-0.5]}).to_csv(tmp_path / "t.csv", index=False)
    pd.DataFrame({"sym": ["S01"], "r": [-0.5]}).to_csv(tmp_path / "bad.csv", index=False)
    base = ["--ohlcv", str(tmp_path / "p.csv"), "--scores", str(tmp_path / "s.csv"), "--signal-only", "--format", "json"]
    code = main([*base, "--liquid-top", "6", "--rebalance-phase", "0/3", "--terminal-returns", str(tmp_path / "t.csv")])
    out = capsys.readouterr().out
    assert code in (0, 1) and '"delisting_returns"' in out
    with pytest.raises(ValueError, match="symbol and return"):
        main([*base, "--terminal-returns", str(tmp_path / "bad.csv")])
