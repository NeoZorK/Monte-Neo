"""Strategy Lab track 2: ETF ideas with canonical literature parameters. Pure functions of a price panel, no network, no trading.

Every idea maps (adjusted close panel, close panel, params) -> target weights at the close of day t (computed from data up to t).
``backtest`` applies them on day t+1 (next bar), charges costs on turnover and a borrow fee on shorts. Leverage is capped at 1.0 gross.
Not investment advice.
"""

from __future__ import annotations

import itertools
from typing import Any

import numpy as np
import pandas as pd

UNIVERSE = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "SHY", "LQD", "HYG", "GLD", "SLV", "DBC", "USO", "UUP", "VNQ"]
BONDS = ["TLT", "IEF", "LQD", "HYG"]
COST_BPS, BORROW_BPS_YEAR, PPY, REBAL_DAYS = 3.0, 50.0, 252, 21
DISC_END, VAL_END = pd.Timestamp("2014-12-31"), pd.Timestamp("2020-12-31")  # holdout = after VAL_END (sealed)


def _rebal_mask(index: pd.DatetimeIndex) -> pd.Series:
    """Last trading day of each calendar month."""
    m = pd.Series(index.to_period("M"), index=index)
    return m != m.shift(-1)


def _vol(px: pd.DataFrame, win: int) -> pd.DataFrame:
    return px.pct_change(fill_method=None).rolling(win, min_periods=win).std() * np.sqrt(PPY)


def tsmom_vol_target(px, close, lookback=252, vol_win=60, asset_vol=0.40, port_vol=0.10):
    """Moskowitz-Ooi-Pedersen: sign of the past return, sized to a vol target; equal-risk average over assets."""
    sig = np.sign(px.pct_change(lookback, fill_method=None))
    w = sig * (asset_vol / _vol(px, vol_win))
    n = px.notna().sum(axis=1).replace(0, np.nan)
    w = w.div(n, axis=0) * (port_vol / asset_vol) * 1.0
    return w


def xs_momentum(px, close, lookback=252, skip=21, top_frac=1 / 3):
    """Cross-asset 12-1 momentum, long-only top third, equal weight."""
    r = px.shift(skip).pct_change(lookback - skip, fill_method=None)
    rk = r.rank(axis=1, ascending=False, method="first")
    k = (r.notna().sum(axis=1) * top_frac).round().clip(lower=1)
    sel = rk.le(k, axis=0) & r.notna()
    return sel.astype(float).div(sel.sum(axis=1).replace(0, np.nan), axis=0)


def risk_parity(px, close, vol_win=60):
    """Inverse-vol weights, long-only, fully invested."""
    iv = 1.0 / _vol(px, vol_win)
    return iv.div(iv.sum(axis=1), axis=0)


def bond_trend_carry(px, close, lookback=252):
    """Hold a bond ETF if its trend is positive and its trailing distribution yield beats SHY's; the rest sits in SHY."""
    ret = px.pct_change(lookback, fill_method=None)
    pret = close.pct_change(lookback, fill_method=None)
    yld = ret - pret  # reinvested distributions over the window = carry proxy
    ok = pd.DataFrame(False, index=px.index, columns=BONDS)
    for b in BONDS:
        ok[b] = (ret[b] > 0) & (yld[b] > yld["SHY"])
    w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    cnt = ok.sum(axis=1)
    for b in BONDS:
        w[b] = ok[b] / len(BONDS)
    w["SHY"] = (len(BONDS) - cnt) / len(BONDS)
    return w.where(ret[BONDS].notna().all(axis=1) & yld["SHY"].notna())


def dual_momentum(px, close, lookback=252):
    """Antonacci: winner of SPY vs EFA if it beats SHY over the lookback, else IEF (bond proxy)."""
    r = px.pct_change(lookback, fill_method=None)
    win = np.where(r["SPY"] >= r["EFA"], "SPY", "EFA")
    w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    best = pd.Series(np.where(win == "SPY", r["SPY"], r["EFA"]), index=px.index)
    on = best > r["SHY"]
    for a in ("SPY", "EFA"):
        w[a] = ((win == a) & on).astype(float)
    w["IEF"] = (~on).astype(float)
    return w.where(r[["SPY", "EFA", "SHY"]].notna().all(axis=1))


IDEAS: dict[str, dict[str, Any]] = {
    "etf_tsmom_voltarget": {"fn": tsmom_vol_target, "params": {"lookback": 252, "vol_win": 60, "asset_vol": 0.40, "port_vol": 0.10},
                            "grid": {"lookback": [126, 189, 252, 315, 378]}, "ref": "Moskowitz, Ooi, Pedersen 2012"},
    "etf_xs_momentum": {"fn": xs_momentum, "params": {"lookback": 252, "skip": 21, "top_frac": 1 / 3},
                        "grid": {"lookback": [126, 189, 252]}, "ref": "Jegadeesh, Titman 1993 (12-1)"},
    "etf_risk_parity": {"fn": risk_parity, "params": {"vol_win": 60}, "grid": {"vol_win": [60, 126, 252]}, "ref": "inverse-volatility, Asness et al. 2012"},
    "etf_bond_trend_carry": {"fn": bond_trend_carry, "params": {"lookback": 252}, "grid": {"lookback": [126, 252]}, "ref": "trend + carry in bonds, Asness, Moskowitz, Pedersen 2013"},
    "etf_dual_momentum": {"fn": dual_momentum, "params": {"lookback": 252}, "grid": {"lookback": [126, 189, 252]}, "ref": "Antonacci 2014 (GEM)"},
}


def combos(grid: dict[str, list]) -> list[dict]:
    return [dict(zip(grid, v)) for v in itertools.product(*grid.values())]


def etf_trials() -> int:
    return sum(len(combos(i["grid"])) for i in IDEAS.values())


def backtest(name: str, px: pd.DataFrame, close: pd.DataFrame, params: dict | None = None, cost_bps: float = COST_BPS,
             borrow_bps: float = BORROW_BPS_YEAR) -> pd.Series:
    """Daily net returns. Weights decided at the close of t (monthly), applied to day t+1 returns."""
    idea = IDEAS[name]
    p = {**idea["params"], **(params or {})}
    w_raw = idea["fn"](px, close, **p)
    reb = _rebal_mask(px.index)
    w = w_raw.where(reb).ffill().fillna(0.0)
    gross = w.abs().sum(axis=1)
    w = w.div(gross.clip(lower=1.0), axis=0)  # leverage cap 1.0
    ret = px.pct_change(fill_method=None).fillna(0.0)
    wl = w.shift(1).fillna(0.0)  # next bar
    gross_ret = (wl * ret).sum(axis=1)
    turn = wl.diff().abs().sum(axis=1).fillna(0.0)
    short = (-wl.clip(upper=0)).sum(axis=1)
    net = gross_ret - turn * cost_bps / 1e4 - short * borrow_bps / 1e4 / PPY
    first = w_raw.dropna(how="all").index.min()
    return net[net.index >= first] if pd.notna(first) else net.iloc[0:0]
