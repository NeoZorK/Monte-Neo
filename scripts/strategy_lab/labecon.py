"""Strategy Lab economics: an independent, cost-aware daily P&L for every idea, in plain pandas (no verifier involved).

It answers what the certificates do not: how much of the return is BTC beta, what the net Sharpe is with realistic Binance
costs and with the costs doubled, and how the result splits by calendar year (bull and bear regimes). Funding of perpetual
shorts in the long-short ideas is not modelled (stated in every report). Not investment advice.
"""

from __future__ import annotations

import sys
from typing import Any

import labcore as lc
import numpy as np
import pandas as pd

sys.path.insert(0, str(lc.STRATS / "_common"))
from binance_costs import side_frac  # noqa: E402


def _btc(cut: pd.Timestamp | None) -> pd.Series:
    d = lc.load_series("spot", "BTCUSDT", cut)
    return d.set_index("timestamp")["close"].pct_change()


def _weights(mod, meta: dict[str, Any], pan: dict[str, pd.DataFrame], offset: int = 0, hedge: bool | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Target weights held over each day (decided at the previous close) and the daily returns of the same columns."""
    close = pd.DataFrame({s: d.set_index("timestamp")["close"] for s, d in pan.items()}).sort_index()
    ret = close.pct_change()
    sc = mod.scores(pan, **{k: v for k, v in meta["params"].items() if k != "horizon"})
    wide = sc.pivot(index="timestamp", columns="symbol", values="score").reindex(close.index)
    if meta.get("portfolio", "long_short") == "long_short":
        r = wide.rank(axis=1, pct=True)
        lo, hi = (r <= 1 / 3).astype(float), (r > 2 / 3).astype(float)
        w = hi.div(hi.sum(axis=1).replace(0, np.nan), axis=0).fillna(0) * 0.5 - lo.div(lo.sum(axis=1).replace(0, np.nan), axis=0).fillna(0) * 0.5
    else:  # long_flat: equal weight of capital over the coins that trade, in cash when the score is not positive
        n = close.notna().sum(axis=1).replace(0, np.nan)
        w = (wide > 0).astype(float).div(n, axis=0).fillna(0)
    if meta.get("hedge_btc") if hedge is None else hedge:
        btc = ret["BTCUSDT"]
        beta = ret.rolling(90).cov(btc).div(btc.rolling(90).var(), axis=0).fillna(0)
        w = w.copy()
        w["BTCUSDT"] = w.get("BTCUSDT", 0) - (w.drop(columns="BTCUSDT", errors="ignore") * beta.drop(columns="BTCUSDT")).sum(axis=1)
    mask = pd.Series((np.arange(len(close)) - offset) % int(meta["horizon"]) == 0, index=close.index)
    held = w.where(mask).ffill().fillna(0).shift(1).fillna(0)  # rebalanced every `horizon` days at the close, earns from the next bar
    return held, ret


def net_returns(name: str, cut: pd.Timestamp | None, cost_mult: float = 1.0, pan: dict | None = None, offset: int = 0, hedge: bool | None = None) -> pd.Series | None:
    mod = lc.load_module(name)
    meta = mod.META
    if meta["kind"] == "alpha":
        if pan is None:
            pan = {s: d for s in meta["universe"] if (d := lc.load_series("spot", s, cut)) is not None}
        held, ret = _weights(mod, meta, pan, offset, hedge)
        venue = "spot" if meta.get("portfolio") == "long_flat" else "perp"
        fee = pd.Series({s: side_frac(s, venue, cost_mult) for s in held.columns})
        cost = held.diff().abs().fillna(0).mul(fee, axis=1).sum(axis=1)
        return ((held * ret.reindex(columns=held.columns).fillna(0)).sum(axis=1) - cost).rename("net")
    if meta["kind"] == "returns":
        try:
            return mod.returns(lc.panel(meta, cut), **meta["params"], **({"cost_mult": cost_mult} if cost_mult != 1.0 else {})).rename("net")
        except TypeError:
            return None if cost_mult != 1.0 else mod.returns(lc.panel(meta, cut), **meta["params"]).rename("net")
    df = lc.load_series("spot", meta["asset"].split("_")[1], cut)  # verify kind: the signal file, next-bar fills
    pos = pd.Series(np.nan_to_num(mod.signal(df, **meta["params"])), index=df["timestamp"]).shift(1).fillna(0)
    c = (lc.COMMISSION_BPS + lc.SLIPPAGE_BPS) / 1e4 * cost_mult
    return (pos * df.set_index("timestamp")["close"].pct_change().fillna(0) - pos.diff().abs().fillna(0) * c).rename("net")


def _sharpe(r: pd.Series) -> float | None:
    r = r.dropna()
    return round(float(r.mean() / r.std() * np.sqrt(lc.PPY)), 3) if len(r) > 30 and r.std() > 0 else None


def metrics(net: pd.Series, bench: pd.Series, n_trials: int) -> dict[str, Any]:
    from monte_neo.verify.stats import deflated_sharpe

    net = net.dropna()
    if len(net) < 60 or net.std() == 0:
        return {"bars": int(len(net))}
    b = bench.reindex(net.index).fillna(0)
    corr = float(np.corrcoef(net, b)[0, 1]) if b.std() > 0 else float("nan")
    beta = float(np.cov(net, b)[0, 1] / b.var()) if b.var() > 0 else float("nan")
    resid = net - beta * b
    t_alpha = float(resid.mean() / (resid.std() / np.sqrt(len(resid)))) if resid.std() > 0 else float("nan")
    eq = (1 + net).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    ds = deflated_sharpe(net.to_numpy(float), n_trials=n_trials, periods_per_year=lc.PPY)
    return {"bars": int(len(net)), "sharpe": _sharpe(net), "total_return": round(float(eq.iloc[-1] - 1), 4), "max_drawdown": round(dd, 4),
            "corr_btc": round(corr, 3), "beta_btc": round(beta, 3), "beta_share": round(corr**2, 3), "alpha_t_vs_btc": round(t_alpha, 2),
            "deflated_sharpe": round(float(ds["deflated_sharpe"]), 3), "btc_buyhold_sharpe": _sharpe(b)}


def economics(name: str, n_trials: int) -> dict[str, Any]:
    """Cost-aware P&L on everything before the holdout (the holdout is never read), split into discovery and validation, with cost x2."""
    cut = lc.HOLD_START
    bench = _btc(cut)
    base, dbl = net_returns(name, cut), net_returns(name, cut, 2.0)
    if base is None:
        return {"note": "no economics available"}
    base.index, bench.index = pd.to_datetime(base.index).tz_localize(None), pd.to_datetime(bench.index).tz_localize(None)
    val, disc = base[base.index >= lc.VAL_START], base[base.index < lc.VAL_START]
    out: dict[str, Any] = {"validation": metrics(val, bench, n_trials), "discovery": metrics(disc, bench, n_trials)}
    if dbl is not None:
        dbl.index = pd.to_datetime(dbl.index).tz_localize(None)
        out["cost_x2_sharpe_validation"] = _sharpe(dbl[dbl.index >= lc.VAL_START])
        out["cost_x2_sharpe_discovery"] = _sharpe(dbl[dbl.index < lc.VAL_START])
    out["by_year"] = {str(y): {"sharpe": _sharpe(g), "return": round(float((1 + g).prod() - 1), 3), "btc_return": round(float((1 + bench.reindex(g.index).fillna(0)).prod() - 1), 3)}
                      for y, g in base.groupby(base.index.year)}
    out["notes"] = ["daily bars, fills at the next close, per-coin Binance fees + spread (VIP0), no funding on perpetual shorts, survivors-only universe"]
    return out
