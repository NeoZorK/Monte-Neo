#!/usr/bin/env python
"""Case generator and runner for the calibration of the Alpha Readiness Level (ARL).

Use run.sh (setup, replicate, start, status, aggregate). Environment:
  MONTE_NEO_RC     checkout of Monte-Neo at the frozen tag (required)
  ARL_CALIB_OUT    output directory (required)
  ARL_BARS         daily bars parquet for the real-data noise cases (required)
  ARL_BASE_SEED    base seed (20261119 = development runs; the confirmatory run uses 20261128)
  ARL_ARM          "parity": every case gets the same artefacts (a fresh trial ledger; on the cross-sectional track a
                   fixed-universe membership file when the case declares none). "silent": the development design, in
                   which the hidden-trials trap keeps no ledger and the cross-sectional traps get no added membership
                   file.
  ARL_ZOO_SEEDS    "full": zoo cases use the full case seed. "mod1000": the development design (seed modulo 1,000).

Populations (one row per case, one JSON file per case in OUT/cases/, so a run is resumable):
  A  traps         look-ahead (shift, centred window, full-sample z-score), cost omission, hidden trials (best of 100 or
                   1,000 noise strategies reported as one trial), regime decay, survivorship, phantom pairs P&L, and
                   thirteen cross-sectional traps. Each has a maximum level fixed by design (truth_max_level).
  B  noise         noise strategies or scores, best of K with the honest K, on random walks and on daily bars of real markets (crypto, FX,
                   index and commodity series; see bars_manifest.csv).
  C  planted edge  single asset (net Sharpe 0.5/1/1.5/2 x 1/3/5/10 years), cross-section (edges E1..E4 x 1/3/5/10
                   years), and the honest twins of the zoo traps.
Tracks: V = verify_strategy / verify_returns (single strategy); X = validate_alpha (cross-section).
Case i is a pure function of (i, base seed): a longer run extends a shorter one with the same prefix.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import os
import platform
import signal
import sys
import time
import traceback
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

RC = Path(os.environ.get("MONTE_NEO_RC", "monte-neo")).resolve()
sys.path[:0] = [str(RC / "src"), str(RC / "tests" / "zoo")]
OUT = Path(os.environ.get("ARL_CALIB_OUT", "out"))
REAL = Path(os.environ.get("ARL_BARS", "bars_1d.parquet"))
BASE_SEED = int(os.environ.get("ARL_BASE_SEED", "20261119"))
ARM = os.environ.get("ARL_ARM", "silent")
ZOO_SEEDS = os.environ.get("ARL_ZOO_SEEDS", "mod1000")
if ARM not in ("parity", "silent") or ZOO_SEEDS not in ("full", "mod1000"):
    raise SystemExit(f"bad ARL_ARM={ARM!r} or ARL_ZOO_SEEDS={ZOO_SEEDS!r}")
PPY = 365.0
COST_BPS = 10.0  # verify default: per side
YEARS = (1, 3, 5, 10)
SHARPES = (0.5, 1.0, 1.5, 2.0)
EDGES = {"E1": 0.0003, "E2": 0.0006, "E3": 0.0009, "E4": 0.0012}  # cross-section edge per unit of score
KS = (1, 10, 100, 1000)

# ---------------------------------------------------------------------------------------------------------------- cells
# (group, weight %, cells); a cell is a dict of the case parameters; the seed index cycles through the cells.
A_KINDS = [("lookahead_shift", 1), ("lookahead_centered", 1), ("global_zscore", 1), ("cost_omission", 2), ("hidden_trials", 2),
           ("regime_decay", 2), ("survivor_universe", 1), ("phantom_pairs", 1)]
ZOO = ["repackaged_momentum", "short_volatility", "three_symbols", "first_day_of_month", "illiquid_shorts", "survivor_universe",
       "membership_window", "same_date_new_york", "dies_after_discovery", "noise_score", "book_clone", "exact_values", "inflated_claim"]


def cells_for(group: str, quick: bool) -> list[dict[str, Any]]:
    ys = (1, 3) if quick else YEARS
    ks = (1, 10, 100) if quick else KS
    if group == "VA":
        return [{"kind": k, "years": y, "truth_max_level": {"lookahead_shift": 1, "lookahead_centered": 1, "global_zscore": 1,
                "cost_omission": 2, "hidden_trials": 3, "regime_decay": 6, "survivor_universe": 4, "phantom_pairs": 2}[k]}
                for k, w in A_KINDS for _ in range(w) for y in ys]
    if group == "XA":
        return [{"kind": "zoo_trap:" + z, "zoo": z, "trap": True, "truth_max_level": 4} for z in ZOO]
    if group == "VB":
        return [{"kind": f"null_{d}", "data": d, "K": k, "years": y, "truth_max_level": 3} for d in ("sim", "real") for k in ks for y in ys]
    if group == "XB":
        return [{"kind": "null_scores", "K": k, "years": y, "truth_max_level": 3} for k in (1, 10, 50) for y in ys]
    if group == "VC":
        return [{"kind": "planted", "sharpe": s, "years": y, "n_trials": nt, "truth_max_level": 9} for s in SHARPES for y in ys for nt in (1, 20)]
    if group == "XC":
        c = [{"kind": f"planted_{e}", "edge": v, "years": y, "book": b, "truth_max_level": 9} for e, v in EDGES.items() for y in ys for b in (False, True)]
        return c + [{"kind": "zoo_twin:" + z, "zoo": z, "trap": False, "truth_max_level": 9} for z in ZOO]
    raise KeyError(group)


GROUPS = [("VA", 14), ("XA", 10), ("VB", 14), ("XB", 8), ("VC", 32), ("XC", 22)]
POP = {"VA": "A", "XA": "A", "VB": "B", "XB": "B", "VC": "C", "XC": "C"}


def schedule(n: int) -> list[str]:
    """A fixed 100-slot pattern (largest remainder, interleaved) repeated to n slots."""
    slots, acc = [], {g: 0.0 for g, _ in GROUPS}
    for _ in range(100):
        for g, w in GROUPS:
            acc[g] += w / 100
        g = max(acc, key=lambda k: acc[k])
        acc[g] -= 1
        slots.append(g)
    return [slots[i % 100] for i in range(n)]


def build_cases(n: int, quick: bool) -> list[dict[str, Any]]:
    sched, counter, out = schedule(n), {g: 0 for g, _ in GROUPS}, []
    cells = {g: cells_for(g, quick) for g, _ in GROUPS}
    for i, g in enumerate(sched):
        j = counter[g]
        counter[g] += 1
        cell = dict(cells[g][j % len(cells[g])])
        seed = int(np.random.SeedSequence([BASE_SEED, i]).generate_state(1)[0] % (2**31))
        out.append({"id": f"{i:06d}_{g}", "i": i, "group": g, "population": POP[group_of(g)], "track": g[0], "rep": j // len(cells[g]),
                    "seed": seed, "quick": quick, **cell})
    return out


def group_of(g: str) -> str:
    return g


# -------------------------------------------------------------------------------------------------------------- data
def ar1(rng: np.random.Generator, n: int, phi: float) -> np.ndarray:
    u = rng.standard_normal(n) * math.sqrt(1 - phi * phi)
    out = np.empty(n)
    out[0] = rng.standard_normal()
    for t in range(1, n):
        out[t] = phi * out[t - 1] + u[t]
    return out


def ohlcv_from_close(c: np.ndarray, rng: np.random.Generator, start: str = "2020-01-01") -> pd.DataFrame:
    o = np.r_[c[0], c[:-1]]
    ts = pd.date_range(start, periods=len(c), freq="D", tz="UTC")
    return pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) * 1.003, "low": np.minimum(o, c) * 0.997, "close": c,
                         "volume": 1e6 * np.exp(0.3 * rng.standard_normal(len(c)))})


def planted_frame(n: int, k: float, rng: np.random.Generator, phi: float = 0.9, sigma: float = 0.012, k_after: float | None = None):
    s = ar1(rng, n, phi)
    kk = np.full(n, k)
    if k_after is not None:
        kk[n // 2:] = k_after
    r = np.zeros(n)
    r[1:] = sigma * (kk[:-1] * s[:-1] + rng.standard_normal(n)[1:])
    df = ohlcv_from_close(100 * np.exp(np.cumsum(r)), rng)
    df["feat"] = s
    return df


def k_for_sharpe(target: float, phi: float = 0.9, sigma: float = 0.012) -> float:
    """Edge k so that sign(s) earns net Sharpe ~ target: flip prob arccos(phi)/pi, 2 sides of 10 bps per flip, E|s| = 0.8."""
    flip = math.acos(phi) / math.pi
    cost = flip * 2 * COST_BPS * 1e-4
    return (target * sigma / math.sqrt(PPY) + cost) / (0.8 * sigma)


_REAL: pd.DataFrame | None = None
_LAST_SERIES = -1


def real_window(n: int, rng: np.random.Generator) -> pd.DataFrame:
    global _REAL
    if _REAL is None:
        d = pd.read_parquet(REAL)
        _REAL = d
    d = _REAL
    sizes = d.groupby("series_id").size()
    ok = sizes[sizes >= n].index.to_numpy()
    if len(ok) == 0:
        ok = sizes.sort_values().index[-5:].to_numpy()
    sid = int(rng.choice(ok))
    global _LAST_SERIES
    _LAST_SERIES = sid
    g = d[d["series_id"] == sid].sort_values("ts").reset_index(drop=True)
    st = int(rng.integers(0, max(1, len(g) - n + 1)))
    g = g.iloc[st:st + n].rename(columns={"ts": "timestamp"})[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    g["timestamp"] = pd.to_datetime(g["timestamp"], utc=True)
    return g.reset_index(drop=True)


def best_noise_feature(close: np.ndarray, k: int, rng: np.random.Generator) -> tuple[np.ndarray, float]:
    """Best of K AR(1) noise signals by in-sample net Sharpe (grid search on noise); returns the feature and its Sharpe."""
    n = len(close)
    ret = np.r_[np.diff(close) / close[:-1], 0.0]  # return earned by the position held after bar t
    best, best_sh = None, -1e9
    for lo in range(0, k, 100):
        m = min(100, k - lo)
        f = np.stack([ar1(rng, n, 0.9) for _ in range(m)])
        pos = np.sign(f)
        cost = COST_BPS * 1e-4 * np.abs(np.diff(pos, axis=1, prepend=0.0))
        pnl = pos * ret - cost
        sh = pnl.mean(1) / (pnl.std(1) + 1e-12)
        a = int(sh.argmax())
        if sh[a] > best_sh:
            best, best_sh = f[a].copy(), float(sh[a])
    return best, best_sh * math.sqrt(PPY)


# ------------------------------------------------------------------------------------------------------- strategies
def sig_feat(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["feat"].to_numpy())


def sig_shift(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["close"].shift(-1) - df["close"]).fillna(0).to_numpy()


def sig_centered(df: pd.DataFrame) -> np.ndarray:
    return np.sign(df["close"].rolling(5, center=True, min_periods=1).mean() - df["close"]).to_numpy()


def sig_gz(df: pd.DataFrame) -> np.ndarray:
    return -np.sign((df["close"] - df["close"].mean()) / df["close"].std()).to_numpy()


def sig_ones(df: pd.DataFrame) -> np.ndarray:
    return np.ones(len(df))


# ------------------------------------------------------------------------------------------------------------ runners
def _case_ledger() -> str:
    """A fresh, empty trial ledger for one case (the case's own variant is its only entry)."""
    import tempfile

    return str(Path(tempfile.mkdtemp(prefix="arl_ledger_")) / "ledger.jsonl")


def run_v(c: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], int, dict[str, Any]]:
    """Single-asset case -> (certificate, readiness inputs: n_trials, planted info)."""
    from monte_neo.verify import verify_strategy

    rng = np.random.default_rng(c["seed"])
    n = int(c.get("years", 3) * 365)
    kind, info, nt = c["kind"], {}, int(c.get("n_trials", 1))
    kw: dict[str, Any] = {"periods_per_year": PPY}
    if kind == "planted":
        k = k_for_sharpe(c["sharpe"])
        df, fn = planted_frame(n, k, rng), sig_feat
        info = {"planted_net_sharpe": c["sharpe"], "planted_k": k}
    elif kind == "regime_decay":
        k = k_for_sharpe(2.0)
        df, fn = planted_frame(n, k, rng, k_after=0.0), sig_feat
        info = {"planted_net_sharpe": 2.0, "planted_k": k, "note": "edge in first half only"}
    elif kind == "cost_omission":
        s = rng.standard_normal(n)  # white signal: flips half the bars; gross edge ~ 6 bps/bar, costs ~ 10 bps/bar
        sigma = 0.012
        r = np.zeros(n)
        r[1:] = sigma * (0.0006 / (0.8 * sigma) * s[:-1] + rng.standard_normal(n)[1:])
        df = ohlcv_from_close(100 * np.exp(np.cumsum(r)), rng)
        df["feat"], fn = s, sig_feat
        info = {"planted_gross_bps_per_bar": 6.0, "note": "gross edge smaller than costs"}
    elif kind in ("lookahead_shift", "lookahead_centered", "global_zscore"):
        r = 0.012 * rng.standard_normal(n)
        df = ohlcv_from_close(100 * np.exp(np.cumsum(r)), rng)
        fn = {"lookahead_shift": sig_shift, "lookahead_centered": sig_centered, "global_zscore": sig_gz}[kind]
    elif kind in ("hidden_trials", "null_sim", "null_real"):
        r = 0.012 * rng.standard_normal(n)
        df = real_window(n, rng) if kind == "null_real" else ohlcv_from_close(100 * np.exp(np.cumsum(r)), rng)
        k = int(c.get("K", 100 if kind == "hidden_trials" else 1))
        if kind == "hidden_trials":
            k = int(rng.choice([100, 1000] if not c["quick"] else [50, 100]))
        feat, ish = best_noise_feature(df["close"].to_numpy(), k, rng)
        df["feat"], fn = feat, sig_feat
        nt = 1 if kind == "hidden_trials" else k
        info = {"K_candidates": k, "best_in_sample_sharpe": ish}
        if kind == "null_real":
            info["series_id"] = _LAST_SERIES
    elif kind == "survivor_universe":
        days = pd.bdate_range("2019-01-01", periods=int(c["years"] * 252))
        fr = []
        for j in range(6):
            cl = 40 * np.exp(np.cumsum(rng.normal(0.0008, 0.015, len(days))))
            o = np.r_[cl[0], cl[:-1]]
            fr.append(pd.DataFrame({"timestamp": days, "symbol": f"S{j}", "open": o, "high": np.maximum(o, cl) * 1.003,
                                    "low": np.minimum(o, cl) * 0.997, "close": cl, "volume": 1e6}))
        df, fn = pd.concat(fr, ignore_index=True), sig_ones
        kw["periods_per_year"] = 252.0
        info = {"note": "all symbols survive and drift up; long all"}
    elif kind == "phantom_pairs":
        from monte_neo.verify.returns_dd import verify_returns
        from monte_neo.verify.phantom import pair_pnl, random_walk_pair

        bars = max(int(c["years"] * 365 * 2), 1500)
        ly, lx = random_walk_pair(bars, 0.01, rng)
        res = pair_pnl(ly, lx, 100)
        ser = pd.Series(res["booked"][101:], index=pd.date_range("2022-01-01", periods=bars - 101, freq="h", tz="UTC"))
        rep = verify_returns(ser, n_strategies=1, periods_per_year=8760.0)
        return rep, {}, 1, {"note": "phantom booking on independent random walks; returns-only evidence"}
    else:
        raise KeyError(kind)
    if ARM == "parity" or kind != "hidden_trials":  # silent design: the hidden-trials trap keeps no ledger
        kw["ledger"] = _case_ledger()
    rep = verify_strategy(df, signal_fn=fn, n_trials=nt, **kw)
    return rep, {}, nt, info


def _fixed_membership(prices: Any) -> Any:
    """Every symbol is a member for the whole period: the declaration an honest fixed universe makes (FX, futures, synthetic)."""
    syms = sorted(set(prices["symbol"])) if "symbol" in getattr(prices, "columns", []) else list(getattr(prices, "columns", []))
    return pd.DataFrame({"symbol": syms, "start": "", "end": ""})


def run_x(c: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], int, dict[str, Any]]:
    import alpha_cases as ac
    from monte_neo.alpha import validate_alpha

    placebos = 40 if c["quick"] else 100
    kind, info, nt = c["kind"], {}, 1
    if kind.startswith("zoo_"):
        data_seed = c["seed"] if ZOO_SEEDS == "full" else c["seed"] % 1000
        case = getattr(ac, c["zoo"])(data_seed, c["trap"])
        kw = {**case.kwargs, "placebos": placebos}
        if (ARM == "parity" or not c["trap"]) and "membership" not in kw:  # declared fixed universe (needed at level 5)
            kw["membership"] = _fixed_membership(case.prices)
        kw["ledger"] = _case_ledger()
        rep = validate_alpha(case.prices, case.scores, seed=c["seed"] % 1000, **kw)
        return rep, {}, int(kw.get("n_trials", 1)), {"zoo": case.name, "trap": c["trap"]}
    rng = np.random.default_rng(c["seed"])
    t = int(c["years"] * 252)
    syms, dates = ac._symbols(30), ac._dates(t)
    if kind == "null_scores":
        a, fwd = ac._plain(rng, 0.0, t=t, n=30)
        k = int(c["K"])
        close = ac._close(fwd)
        best, bq = None, -1e9
        nxt = np.vstack([close[1:] / close[:-1] - 1, np.zeros((1, 30))])
        for _ in range(k):  # best of K noise scores by in-sample cross-sectional rank IC (grid search on noise)
            sc = ac._ar1(rng, t, 30, 0.9)
            ic = np.nanmean([np.corrcoef(sc[i], nxt[i])[0, 1] for i in range(0, t - 1, 3)])
            if ic > bq:
                best, bq = sc, ic
        scores, nt, info = best, k, {"K_candidates": k, "best_in_sample_ic": float(bq)}
        book = None
    else:
        edge = float(c["edge"])
        a, fwd = ac._plain(rng, edge, t=t, n=30)
        scores, book = a, None
        info = {"planted_edge": edge, "nominal_label": c["kind"].split("_")[1]}
        if c.get("book"):
            book = pd.DataFrame({"date": dates, "fund": 0.0005 + 0.006 * rng.standard_normal(t)})
        nt = 1
    prices, score = ac._tables(dates, syms, ac._close(fwd), 1e6, scores)
    kw = {"aum": ac.AUM, "placebos": placebos, "n_trials": nt, "membership": _fixed_membership(prices)}
    if book is not None:
        kw["book"] = book
    kw["ledger"] = _case_ledger()
    rep = validate_alpha(prices, score, seed=c["seed"] % 1000, **kw)
    return rep, {}, nt, info


# ----------------------------------------------------------------------------------------------------- flattening
def scalars(prefix: str, d: dict[str, Any], out: dict[str, Any]) -> None:
    for k, v in (d or {}).items():
        if isinstance(v, bool) or isinstance(v, (int, float, str)) and (not isinstance(v, str) or len(v) < 40):
            out[f"{prefix}{k}"] = v
        elif isinstance(v, (list, tuple)) and 0 < len(v) <= 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
            for q, x in enumerate(v):
                out[f"{prefix}{k}__{q}"] = x


def flatten(rep: dict[str, Any], rd: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {"verdict": rep.get("verdict"), "rules_version": rd["rules_version"], "arl_level": rd["level"], "arl_depth": rd["depth"],
                           "arl_summary": rd["summary"], "n_trials_used": rd["n_trials_used"]}
    scalars("m_", rep.get("metrics") or {}, row)
    chk = {}
    for ch in rep.get("checks", []):
        cid = ch["id"]
        row[f"s_{cid}"] = ch["status"]
        scalars(f"d_{cid}__", ch.get("details") or {}, row)
        chk[cid] = {"status": ch["status"], "category": ch.get("category")}
    first = next((lv for lv in rd["levels"] if lv["state"] != "met"), None)
    row["blocked_level"] = first["level"] if first else 10
    row["blocked_state"] = first["state"] if first else "met"
    row["blocking_rule"] = ";".join(first["blocking"]) if first else ""
    row["caps"] = ";".join(f"{c['check']}<={c['max_level']}" for c in rd.get("ceilings", []))
    for lv in rd["levels"]:
        n = lv["level"]
        row[f"lv{n}_state"] = lv["state"]
        row[f"lv{n}_blocking"] = ";".join(lv["blocking"])
        row[f"lv{n}_depth_if_reached"] = lv["depth_if_reached"]
        for cr in lv["depth_criteria"]:
            row[f"lv{n}_{cr['id']}"] = cr["state"]
    return row


def run_case(c: dict[str, Any]) -> dict[str, Any]:
    warnings.simplefilter("ignore")
    t0 = time.time()
    from monte_neo.readiness import readiness

    def _alarm(*_: Any) -> None:
        raise TimeoutError("case timeout")
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(int(os.environ.get("ARL_CASE_TIMEOUT", "900")))
    try:
        rep, _, nt, info = run_x(c) if c["track"] == "X" else run_v(c)
        if c["track"] == "X":
            rd = readiness(alpha=rep, n_trials=nt)
        else:
            rd = readiness(certificate=rep, n_trials=nt)
        row = flatten(rep, rd)
        row.update({k: v for k, v in c.items() if k not in ("quick",)})
        row.update({"arm": ARM, "base_seed": BASE_SEED, "zoo_seeds": ZOO_SEEDS})
        row["planted_info"] = json.dumps(info)
        row["false_promotion"] = bool(rd["level"] > c["truth_max_level"]) if c["population"] in ("A", "B") else None
        row["seconds"] = round(time.time() - t0, 2)
        row["ok"] = True
    except BaseException as e:  # noqa: BLE001
        row = {**{k: v for k, v in c.items() if k != "quick"}, "ok": False, "error": f"{type(e).__name__}: {e}"[:300],
               "trace": traceback.format_exc()[-1500:], "seconds": round(time.time() - t0, 2)}
    finally:
        signal.alarm(0)
    return row


def worker(c: dict[str, Any]) -> dict[str, Any]:
    global OUT
    OUT = Path(c.pop("_out"))
    row = run_case(c)
    d = OUT / ("cases" if row.get("ok") else "errors")
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{c['id']}.tmp"
    tmp.write_text(json.dumps(row, default=str))
    tmp.rename(d / f"{c['id']}.json")
    if row.get("ok"):
        (OUT / "errors" / f"{c['id']}.json").unlink(missing_ok=True)
    return {"id": c["id"], "ok": row.get("ok"), "seconds": row.get("seconds"), "error": row.get("error")}


# ------------------------------------------------------------------------------------------------------ aggregate
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, ctr - h), min(1.0, ctr + h)


def aggregate() -> None:
    rows = [json.loads(p.read_text()) for p in sorted((OUT / "cases").glob("*.json"))]
    if not rows:
        print("no results yet")
        return
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "results.csv", index=False)
    if platform.machine() == "arm64" and os.environ.get("ARL_PARQUET", "1") == "1":
        try:
            df.astype({c: str for c in df.columns if df[c].dtype == object}).to_parquet(OUT / "results.parquet", index=False)
        except Exception as e:  # noqa: BLE001
            print("parquet skipped:", e)
    if "K" not in df.columns or not {"A", "B", "C"} <= set(df["population"]):
        print(f"{len(df)} cases written to results; no summary for a partial set of cases")
        return
    out = []

    def add(group: str, sub: pd.DataFrame) -> None:
        n = len(sub)
        for L in range(1, 10):
            k = int((sub["arl_level"] >= L).sum())
            lo, hi = wilson(k, n)
            out.append({"group": group, "level": L, "n": n, "reached": k, "rate": k / n, "wilson_lo": lo, "wilson_hi": hi})

    for pop in ("A", "B", "C"):
        s = df[df["population"] == pop]
        for tr, ss in [("all", s), *[(t, s[s["track"] == t]) for t in "VX"]]:
            if len(ss):
                add(f"{pop}/{tr}", ss)
        for kind, ss in s.groupby("kind"):
            add(f"{pop}/{ss['track'].iloc[0]}/{kind}", ss)
    for (tr, y), ss in df[df["population"] == "B"].groupby(["track", "years"]):
        add(f"B/{tr}/years={y}", ss)
    for (tr, kd, kk), ss in df[(df["population"] == "B") & df["K"].notna()].groupby(["track", "kind", "K"]):
        add(f"B/{tr}/{kd}/K={int(kk)}", ss)
    c = df[df["population"] == "C"]
    for (tr, y), ss in c.groupby(["track", "years"]):
        add(f"C/{tr}/years={y}", ss)
    for sh, ss in c[c["track"] == "V"].groupby("sharpe"):
        add(f"C/V/sharpe={sh}", ss)
    for (sh, y), ss in c[c["track"] == "V"].groupby(["sharpe", "years"]):
        add(f"C/V/sharpe={sh}/years={y}", ss)
    sm = pd.DataFrame(out)
    sm.to_csv(OUT / "summary_levels.csv", index=False)
    fp = df[df["population"].isin(["A", "B"]) & df["false_promotion"].notna()]
    lines = ["# ARL calibration summary", "", f"cases ok: {len(df)} (errors: {len(list((OUT / 'errors').glob('*.json')))}); rules {df['rules_version'].iloc[0]}", "",
             "Reach rate = share of cases with ARL >= level (Wilson 95% in summary_levels.csv). A/B: false-promotion; C: power.", ""]
    for g in ("A/all", "A/V", "A/X", "B/all", "B/V", "B/X", "C/all", "C/V", "C/X"):
        s = sm[(sm["group"] == g)]
        if len(s):
            lines.append(f"## {g} (n={int(s['n'].iloc[0])})")
            lines.append("| level | " + " | ".join(str(i) for i in s["level"]) + " |")
            lines.append("|---|" + "---|" * len(s))
            lines.append("| rate | " + " | ".join(f"{r:.2f} [{lo:.2f},{hi:.2f}]" for r, lo, hi in zip(s["rate"], s["wilson_lo"], s["wilson_hi"])) + " |")
            lines.append("")
    if len(fp):
        lines.append(f"False promotion (level above truth_max_level) over A and B: {int(fp['false_promotion'].sum())}/{len(fp)}")
        for pop, ss in fp.groupby("population"):
            k, n = int(ss["false_promotion"].sum()), len(ss)
            lo, hi = wilson(k, n)
            lines.append(f"- {pop}: {k}/{n} = {k / n:.3f} [{lo:.3f},{hi:.3f}]")
    lines += ["", "Blocking rule at the next level (count by track and population):"]
    bl = df[df["ok"] == True].groupby(["population", "track", "blocked_level", "blocking_rule"]).size().reset_index(name="n").sort_values("n", ascending=False).head(25)  # noqa: E712
    lines += [f"- {r.population}/{r.track} blocked at L{r.blocked_level} by [{r.blocking_rule}]: {r.n}" for r in bl.itertuples()]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:60]))


# ---------------------------------------------------------------------------------------------------------- main
def default_jobs() -> int:
    return 2 if platform.machine() == "x86_64" else 4


def fmt(s: float) -> str:
    s = int(max(0, s))
    return f"{s // 3600}h{s % 3600 // 60:02d}m{s % 60:02d}s"


def status() -> None:
    p = OUT / "status.json"
    if not p.exists():
        print("no status yet:", p)
        return
    s = json.loads(p.read_text())
    s["age_s"] = int(time.time() - s["updated"])
    print(json.dumps(s, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["run", "dry", "status", "aggregate"])
    ap.add_argument("--n-cases", type=int, default=None)
    ap.add_argument("--quick", action="store_true", help="~5 min: small sizes, years<=3, fewer placebos")
    ap.add_argument("--jobs", type=int, default=default_jobs())
    ap.add_argument("--retry-errors", action="store_true")
    ap.add_argument("--asymmetric-only", action="store_true", help="only the cases whose inputs differ between arms")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    global OUT
    OUT = Path(a.out) if a.out else (OUT / "quick" if a.quick else OUT)
    if a.cmd == "status":
        return status()
    if a.cmd == "aggregate":
        return aggregate()
    n = a.n_cases or (QUICK_N if a.quick else DEFAULT_N)
    cases = build_cases(n, a.quick)
    if a.asymmetric_only:  # the cases whose inputs differ between the two arms
        cases = [c for c in cases if c["kind"] == "hidden_trials" or c["kind"].startswith("zoo_trap:")]
        n = len(cases)
    if a.cmd == "dry":
        import collections
        print("cases:", n, "| by group:", dict(collections.Counter(c["group"] for c in cases)))
        print("kinds:", dict(collections.Counter(c["kind"] for c in cases)))
        pick = {}
        for c in cases:
            pick.setdefault(c["group"], c)
        import tempfile
        OUT = Path(tempfile.mkdtemp(prefix="arl_dry_"))
        for c in pick.values():
            r = run_case(c)
            print(c["id"], c["kind"], "->", ("ARL %s depth %s %.1fs | %s" % (r["arl_level"], r["arl_depth"], r["seconds"], r["arl_summary"])) if r["ok"] else ("ERROR " + r["error"]))
            if not r["ok"]:
                print(r["trace"])
        return
    (OUT / "cases").mkdir(parents=True, exist_ok=True)
    (OUT / "errors").mkdir(exist_ok=True)
    done = {p.stem for p in (OUT / "cases").glob("*.json")}
    if not a.retry_errors:
        done |= {p.stem for p in (OUT / "errors").glob("*.json")}
    todo = [c for c in cases if c["id"] not in done]
    (OUT / "run.pid").write_text(str(os.getpid()))
    log = (OUT / "calib.log").open("a")

    def say(msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()
    t0, finished, secs = time.time(), len(done & {c["id"] for c in cases}), []
    say(f"start: {n} cases, {len(todo)} to do, jobs={a.jobs}, out={OUT}, quick={a.quick}")
    with cf.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(worker, {**c, "_out": str(OUT)}): c for c in todo}
        for f in cf.as_completed(futs):
            try:
                r = f.result()
            except Exception as e:  # noqa: BLE001  (a crashed worker process)
                r = {"id": futs[f]["id"], "ok": False, "seconds": 0, "error": f"worker crash {e}"}
            finished += 1
            secs.append(r["seconds"] or 0)
            el = time.time() - t0
            doneN = len(secs)
            eta = el / doneN * (len(todo) - doneN)
            pct = 100 * finished / n
            bar = "#" * int(pct / 4) + "." * (25 - int(pct / 4))
            say(f"[{bar}] {pct:5.1f}% {finished}/{n} last={r['id']} {r['seconds']}s ok={r['ok']} ETA {fmt(eta)} (~{time.strftime('%H:%M', time.localtime(time.time() + eta))}){' ERR ' + str(r['error']) if not r['ok'] else ''}")
            (OUT / "status.json").write_text(json.dumps({"finished": finished, "total": n, "pct": round(pct, 1), "eta_s": int(eta), "avg_s_per_case_wall": round(el / doneN, 2),
                                                          "avg_s_per_case_cpu": round(sum(secs) / doneN, 2), "jobs": a.jobs, "updated": time.time(), "out": str(OUT)}))
    say("all done; aggregating")
    aggregate()


QUICK_N = 2400
DEFAULT_N = 350000  # about 0.09 s wall per case at --jobs 8 on an Apple M1 Pro

if __name__ == "__main__":
    main()
