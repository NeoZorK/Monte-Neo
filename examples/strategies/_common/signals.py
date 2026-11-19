"""Signal grammar of the Strategy Lab search (rounds 4+): family x parameters x sign, on a daily panel of many coins.

Every function is causal: the value at the close of day t uses data up to and including t. Not investment advice.
`score(close, volume, spec)` returns a (date x symbol) frame; coins outside the point-in-time liquid set (top `top_k` by trailing
60-day median dollar volume, known at t) are NaN, so a coin that lists later enters when it becomes liquid and a delisted coin
leaves when its data ends.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FAMILIES = {  # family: parameter name -> values (declared before any data is looked at)
    "mom": {"lookback": [14, 30, 60, 90, 180], "skip": [0, 7]},
    "rev": {"lookback": [2, 3, 5, 7, 14]},
    "vsmom": {"lookback": [30, 60, 90], "vol_window": [30]},
    "lowvol": {"window": [14, 30, 60, 90]},
    "bab": {"window": [30, 60, 90, 150]},
    "maxl": {"window": [7, 14, 30, 60]},
    "skew": {"window": [30, 60, 90]},
    "hi": {"window": [30, 60, 120, 250]},
    "illiq": {"window": [14, 30, 60]},
    "size": {"window": [30, 90]},
    "voltrend": {"lookback": [5, 14], "volume_window": [60]},
    "range": {"window": [7, 14, 30]},
    "idiovol": {"window": [30, 60, 90]},
}


def eligible(close: pd.DataFrame, volume: pd.DataFrame, top_k: int) -> pd.DataFrame:
    dv = (close * volume).rolling(60, min_periods=45).median()
    rank = dv.rank(axis=1, ascending=False)
    return (rank <= top_k) & (close.notna())


def raw(close: pd.DataFrame, volume: pd.DataFrame, family: str, p: dict) -> pd.DataFrame:
    ret = close.pct_change(fill_method=None)
    btc = ret["BTCUSDT"] if "BTCUSDT" in ret else ret.mean(axis=1)
    if family == "mom":
        return close.shift(p["skip"]) / close.shift(p["skip"] + p["lookback"]) - 1.0
    if family == "rev":
        return close / close.shift(p["lookback"]) - 1.0
    if family == "vsmom":
        return (close / close.shift(p["lookback"]) - 1.0) / (ret.rolling(p["vol_window"]).std() * p["lookback"] ** 0.5)
    if family == "lowvol":
        return ret.rolling(p["window"]).std()
    if family == "bab":
        return ret.rolling(p["window"]).cov(btc).div(btc.rolling(p["window"]).var(), axis=0)
    if family == "maxl":
        return ret.rolling(p["window"]).max()
    if family == "skew":
        return ret.rolling(p["window"]).skew()
    if family == "hi":
        return close / close.rolling(p["window"]).max()
    if family == "illiq":
        return (ret.abs() / (close * volume)).rolling(p["window"]).mean()
    if family == "size":
        return np.log((close * volume).rolling(p["window"]).mean())
    if family == "voltrend":
        dv = close * volume
        return (close / close.shift(p["lookback"]) - 1.0) * (dv.rolling(p["lookback"]).mean() / dv.rolling(p["volume_window"]).mean())
    if family == "range":
        return (close.rolling(p["window"]).max() - close.rolling(p["window"]).min()) / close
    if family == "idiovol":
        beta = ret.rolling(p["window"]).cov(btc).div(btc.rolling(p["window"]).var(), axis=0)
        return (ret.sub(beta.mul(btc, axis=0))).rolling(p["window"]).std()
    return raw_ext(close, volume, ret, btc, family, p)


# ---- Rounds 4+ extension: NEW families only (the families above and their outputs are frozen: batch 1 is pre-registered). ----
FAMILIES_EXT = {  # short a priori grids, declared before any result was looked at
    "resmom": {"lookback": [30, 60, 90, 180], "beta_window": [60, 90]},  # residual momentum vs BTC (Blitz, Huij, Martens 2011)
    "tstrend": {"lookback": [30, 60, 90, 180], "vol_window": [30, 60]},  # sign of trend / realised vol: volatility-managed trend (Moskowitz, Ooi, Pedersen 2012; Barroso, Santa-Clara 2015)
    "strev": {"lookback": [1, 2, 3, 5], "mode": ["volnorm", "lowvolume"]},  # short-term reversal, vol-scaled or on quiet volume (Jegadeesh 1990; Avramov, Chordia, Goyal 2006; Campbell, Grossman, Wang 1993)
    "lowvol2": {"window": [20, 45, 120, 180]},  # low volatility, other windows (Ang et al. 2006)
    "bab2": {"window": [20, 45, 120, 200]},  # betting against beta, other windows (Frazzini, Pedersen 2014)
    "mom2": {"lookback": [60, 90, 180, 270], "skip": [14, 21, 30]},  # momentum skipping the latest days (Jegadeesh, Titman 1993)
    "hi52": {"window": [200, 300, 365], "skip": [0, 7]},  # nearness to the 52-week high (George, Hwang 2004)
    "illiq2": {"window": [20, 45, 90, 150], "agg": ["mean", "median"]},  # Amihud illiquidity premium (Amihud 2002)
}
COMPONENTS = {  # composite building blocks: fixed canonical parameters and sign (+1 = long high score), picked a priori, never tuned
    "M": {"family": "mom2", "params": {"lookback": 90, "skip": 14}, "sign": 1},
    "R": {"family": "resmom", "params": {"lookback": 90, "beta_window": 90}, "sign": 1},
    "V": {"family": "tstrend", "params": {"lookback": 60, "vol_window": 30}, "sign": 1},
    "S": {"family": "strev", "params": {"lookback": 3, "mode": "lowvolume"}, "sign": -1},
    "L": {"family": "lowvol2", "params": {"window": 45}, "sign": -1},
    "B": {"family": "bab2", "params": {"window": 45}, "sign": -1},
    "H": {"family": "hi52", "params": {"window": 365, "skip": 0}, "sign": 1},
    "I": {"family": "illiq2", "params": {"window": 45, "agg": "mean"}, "sign": 1},
    "Z": {"family": "size", "params": {"window": 30}, "sign": -1},
}


def raw_ext(close: pd.DataFrame, volume: pd.DataFrame, ret: pd.DataFrame, btc: pd.Series, family: str, p: dict) -> pd.DataFrame:
    if family == "resmom":
        w = p["beta_window"]
        beta = ret.rolling(w).cov(btc).div(btc.rolling(w).var(), axis=0)
        res = ret.sub(beta.mul(btc, axis=0))
        return res.rolling(p["lookback"]).sum() / res.rolling(p["lookback"]).std()
    if family == "tstrend":
        vol = ret.rolling(p["vol_window"]).std()
        return np.sign(close / close.shift(p["lookback"]) - 1.0) / vol
    if family == "strev":
        r = close / close.shift(p["lookback"]) - 1.0
        if p["mode"] == "volnorm":
            return r / (ret.rolling(30).std() * p["lookback"] ** 0.5)
        dv = close * volume
        return r * (dv.rolling(60).mean() / dv.rolling(p["lookback"]).mean())  # large move on quiet volume weighs more
    if family == "lowvol2":
        return ret.rolling(p["window"]).std()
    if family == "bab2":
        return ret.rolling(p["window"]).cov(btc).div(btc.rolling(p["window"]).var(), axis=0)
    if family == "mom2":
        return close.shift(p["skip"]) / close.shift(p["skip"] + p["lookback"]) - 1.0
    if family == "hi52":
        return close.shift(p["skip"]) / close.rolling(p["window"]).max()
    if family == "illiq2":
        x = ret.abs() / (close * volume)
        return x.rolling(p["window"]).mean() if p["agg"] == "mean" else x.rolling(p["window"]).median()
    raise ValueError(family)


def score(close: pd.DataFrame, volume: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """spec = {"family", "params", "sign" (+1/-1), "top_k"} or {"composite": [spec, ...], "top_k"} (cross-sectional z-score average)."""
    elig = eligible(close, volume, spec["top_k"])
    if "composite" in spec:
        parts = []
        for sub in spec["composite"]:
            s = raw(close, volume, sub["family"], sub["params"]).where(elig) * sub["sign"]
            parts.append(s.sub(s.mean(axis=1), axis=0).div(s.std(axis=1), axis=0))
        out = sum(parts) / len(parts)
    else:
        out = raw(close, volume, spec["family"], spec["params"]).where(elig) * spec["sign"]
    return out.replace([np.inf, -np.inf], np.nan).where(elig)


def long_form(s: pd.DataFrame) -> pd.DataFrame:
    out = s.stack().rename("score").reset_index()
    out.columns = ["timestamp", "symbol", "score"]
    return out.sort_values(["timestamp", "symbol"]).reset_index(drop=True)
