"""Worked ARL examples on synthetic data with known truth (Section "Worked example" of the paper).

Run with Monte-Neo 0.57.0 installed:  python arl_examples.py
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from monte_neo.readiness import readiness
from monte_neo.verify import verify_strategy

DAYS, SIGMA, PHI, COST = 365, 0.012, 0.9, 10e-4  # bars per year, daily volatility, signal persistence, cost per side


def ar1(rng: np.random.Generator, n: int) -> np.ndarray:
    u = rng.standard_normal(n) * math.sqrt(1 - PHI * PHI)
    out = np.empty(n)
    out[0] = rng.standard_normal()
    for t in range(1, n):
        out[t] = PHI * out[t - 1] + u[t]
    return out


def market(rng: np.random.Generator, years: int, edge_sharpe: float = 0.0) -> pd.DataFrame:
    """Daily bars with a column ``feat``; if ``edge_sharpe`` > 0, ``feat`` truly predicts the next return."""
    n = years * DAYS
    s = ar1(rng, n)
    k = 0.0
    if edge_sharpe:
        flip = math.acos(PHI) / math.pi
        k = (edge_sharpe * SIGMA / math.sqrt(DAYS) + flip * 2 * COST) / (0.8 * SIGMA)
    r = np.zeros(n)
    r[1:] = SIGMA * (k * s[:-1] + rng.standard_normal(n)[1:])
    c = 100 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({
        "timestamp": pd.date_range("2015-01-01", periods=n, freq="D", tz="UTC"),
        "open": o, "high": np.maximum(o, c) * 1.003, "low": np.minimum(o, c) * 0.997, "close": c,
        "volume": 1e6 * np.exp(0.3 * rng.standard_normal(n)), "feat": s,
    })


def best_of(df: pd.DataFrame, k: int, rng: np.random.Generator) -> pd.DataFrame:
    """Replace ``feat`` by the best of ``k`` pure-noise signals, selected by in-sample net Sharpe ratio."""
    c = df["close"].to_numpy()
    ret = np.r_[np.diff(c) / c[:-1], 0.0]
    best, best_sh = df["feat"].to_numpy(), -1e9
    for _ in range(k):
        f = ar1(rng, len(df))
        pos = np.sign(f)
        pnl = pos * ret - COST * np.abs(np.diff(pos, prepend=0.0))
        sh = pnl.mean() / pnl.std()
        if sh > best_sh:
            best, best_sh = f, sh
    return df.assign(feat=best)


def follow_feature(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["feat"].to_numpy())


def peek_tomorrow(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["close"].shift(-1) - df["close"]).fillna(0).to_numpy()


def certify(name: str, df: pd.DataFrame, signal, n_trials: int, ledger: bool) -> None:
    kw = {"periods_per_year": float(DAYS)}
    if ledger:
        kw["ledger"] = str(Path(tempfile.mkdtemp()) / "ledger.jsonl")
    cert = verify_strategy(df, signal_fn=signal, n_trials=n_trials, **kw)
    rd = readiness(certificate=cert, n_trials=n_trials)
    rows = {c["id"]: c for c in cert["checks"]}
    sharpe = cert["metrics"]["sharpe_annualized"]
    dsr = rows["deflated_sharpe"]["details"]["deflated_sharpe"]
    print(f"\n{name}\n  net Sharpe {sharpe:.2f}, deflated Sharpe {dsr:.3f}, trials {n_trials}\n  {rd['headline']}")
    for lv in rd["levels"]:
        if lv["level"] == rd["level"]:
            for d in lv["depth_criteria"]:
                print(f"    depth {d['id']} {d['name']:<13} {d['state']:<12} {d['text']}")
        if lv["level"] == rd["level"] + 1:
            print(f"  level {lv['level']} {lv['state']}: {', '.join(lv['blocking'])}")


if __name__ == "__main__":
    rng = np.random.default_rng(7)
    certify("A. uses tomorrow's price", market(rng, 5), peek_tomorrow, 1, True)
    noise = best_of(market(rng, 3), 100, rng)
    certify("B. best of 100 noise signals, search not documented", noise, follow_feature, 1, False)
    certify("C. best of 100 noise signals, 100 trials declared", noise, follow_feature, 100, True)
    certify("D. real edge (target Sharpe 2), 1 year", market(rng, 1, 2.0), follow_feature, 20, True)
    certify("E. real edge (target Sharpe 2), 10 years", market(rng, 10, 2.0), follow_feature, 20, True)
