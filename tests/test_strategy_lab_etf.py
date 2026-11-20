"""Strategy Lab ETF track: loader seal, no look-ahead, costs, trial count (synthetic data, no network)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "strategy_lab"))
import etf_data as ed  # noqa: E402
import etf_ideas as ei  # noqa: E402


@pytest.fixture()
def panel():
    idx = pd.bdate_range("2008-01-01", "2023-06-30")
    rng = np.random.default_rng(1)
    px = pd.DataFrame({s: 50 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(idx)))) for s in ei.UNIVERSE}, index=idx)
    return px, px.copy()


def test_loader_never_reads_sealed(tmp_path, monkeypatch):
    monkeypatch.setattr(ed, "OUT", tmp_path)
    for s in ei.UNIVERSE:
        ed.write_symbol(s, ed.synthetic(s))
    adj, _ = ed.load_panel("2020-12-31")
    assert adj.index.max() <= ei.VAL_END
    with pytest.raises(PermissionError):
        ed.load_panel("2022-01-01")
    assert ed.load_panel("2022-01-01", sealed=True)[0].index.max() > ei.VAL_END


def test_trial_count():
    assert ei.etf_trials() == 16


@pytest.mark.parametrize("name", list(ei.IDEAS))
def test_no_lookahead(panel, name):
    px, cl = panel
    full = ei.backtest(name, px, cl)
    cut = px.index[3000]
    part = ei.backtest(name, px[px.index <= cut], cl[cl.index <= cut])
    common = part.index[part.index <= cut]
    assert np.allclose(full.loc[common].values, part.loc[common].values, atol=1e-12)  # future bars cannot change the past


def test_costs_and_leverage(panel):
    px, cl = panel
    a = ei.backtest("etf_risk_parity", px, cl, cost_bps=0)
    b = ei.backtest("etf_risk_parity", px, cl, cost_bps=10)
    assert b.sum() < a.sum()
    w = ei.risk_parity(px, cl).dropna()
    assert abs(w.sum(axis=1) - 1).max() < 1e-9
