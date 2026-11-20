"""Robustness of ONE candidate before any freeze: survivors, rebalance day, beta, costs, AUM, trials, code-level verify.

    python scripts/strategy_lab/robust.py r2_channel_basket [--threads 3]

Uses only data before the holdout (never reads 2025+). Resumable: every finished run is cached in strategy_lab/work/<name>/robust/.
Writes strategy_lab/results/<name>_robustness.json. Not investment advice; it freezes nothing and decides nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import labcore as lc
import labecon
import numpy as np
import pandas as pd

EXTRA = lc.LAB / "data_extra" / "processed"
EXTRA_SYMS = ["LUNAUSDT", "FTTUSDT", "USTUSDT", "XMRUSDT", "EOSUSDT", "MATICUSDT", "IOTAUSDT", "ZECUSDT", "DASHUSDT", "VETUSDT", "BTTUSDT", "BCCUSDT"]
KEYS = ("ic", "signal_placebo", "residual_alpha", "hidden_short_volatility", "min_backtest_length", "hlz_hurdle", "rebalance_timing_luck", "market_impact",
        "universe_subsampling", "synthetic_market_null", "start_date_sensitivity", "universe_lookahead", "capacity_curve", "short_feasibility")


def load(sym: str, cut: pd.Timestamp) -> pd.DataFrame | None:
    d = lc.load_series("spot", sym, cut)
    if d is not None:
        return d
    p = EXTRA / f"spot_{sym}_1d.parquet"
    if not p.exists():
        return None
    d = pd.read_parquet(p)
    d["timestamp"] = pd.to_datetime(d["timestamp"]).dt.tz_localize(None)
    return d[d["timestamp"] < cut].reset_index(drop=True)


def cached(w: Path, key: str, fn):
    p = w / f"{key}.json"
    if p.exists():
        return json.loads(p.read_text())
    out = fn()
    p.write_text(json.dumps(out, indent=1, default=str))
    return out


def alpha_run(w: Path, key: str, pan: dict, scores: pd.DataFrame, horizon: int, aum: int, n_trials: int, threads: int) -> dict:
    long = pd.concat([d.assign(symbol=s) for s, d in pan.items()])[["timestamp", "symbol", "close", "volume"]]
    long.to_parquet(w / f"{key}_universe.parquet")
    scores.to_parquet(w / f"{key}_scores.parquet")
    mem = pd.DataFrame([(s, d["timestamp"].iloc[0].date().isoformat(), (d["timestamp"].iloc[-1].date().isoformat() if d["timestamp"].iloc[-1] < lc.HOLD_START - pd.Timedelta(days=2) else "2100-01-01"))
                        for s, d in pan.items()], columns=["symbol", "start", "end"])
    mem.to_csv(w / f"{key}_membership.csv", index=False)
    out = w / f"{key}.alpha.json"
    r = lc.mn("alpha", "--ohlcv", str(w / f"{key}_universe.parquet"), "--scores", str(w / f"{key}_scores.parquet"), "--horizon", str(horizon), "--n-trials", str(n_trials),
              "--aum", str(aum), "--membership", str(w / f"{key}_membership.csv"), "--out", str(out), threads=threads)
    if not out.exists():
        return {"error": (r.stderr or r.stdout)[-400:]}
    rep = json.loads(out.read_text())
    rec = lc.summarize(None, rep)
    rd = rep.get("readiness", {})
    nxt = next((x for x in rd.get("levels", []) if x["state"] != "met"), None)
    return {"verdict": rec["verdict"], "arl": rec["arl"], "blocked": (nxt or {}).get("level"), "blocking": (nxt or {}).get("blocking"),
            "checks": {c["id"]: {"status": c["status"], "summary": c["summary"]} for c in rec["checks"] if c["id"] in KEYS}}


def sharpe(r: pd.Series) -> float | None:
    return labecon._sharpe(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--threads", type=int, default=3)
    a = ap.parse_args()
    mod, meta = lc.load_module(a.name), lc.load_module(a.name).META
    cut, h = lc.HOLD_START, int(meta["horizon"])
    w = lc.work(a.name) / "robust"
    w.mkdir(exist_ok=True)
    n_lab = lc.lab_trials()
    n_tr = n_lab + 1  # +1: the BTC-relative variant tried below
    base = {s: d for s in meta["universe"] if (d := load(s, cut)) is not None}
    ext = {**base, **{s: d for s in EXTRA_SYMS if (d := load(s, cut)) is not None}}
    params = {k: v for k, v in meta["params"].items() if k != "horizon"}
    day0 = pd.Timestamp("2017-01-01")

    def thin(sc: pd.DataFrame, off: int) -> pd.DataFrame:
        return sc[((sc["timestamp"] - day0).dt.days % h) == off].reset_index(drop=True)

    sc_base, sc_ext = mod.scores(base, **params), mod.scores(ext, **params)

    def rel_scores(pan: dict) -> pd.DataFrame:  # BTC-relative channel position (a new variant: counted as +1 trial)
        wide = mod.scores(pan, **params).pivot(index="timestamp", columns="symbol", values="score")
        rel = wide.sub(wide["BTCUSDT"], axis=0).drop(columns="BTCUSDT").stack().rename("score").reset_index()
        return rel.dropna()

    # ---- economics (pure pandas, net of per-coin Binance costs)
    ret_b = {s: d.set_index("timestamp")["close"].pct_change() for s, d in base.items()}
    btc = ret_b["BTCUSDT"]
    ew = pd.DataFrame(ret_b).mean(axis=1)

    def econ(pan: dict, off: int = 0, hedge: bool = False, mult: float = 1.0, m=mod, mt=meta) -> dict:
        held, ret = labecon._weights(m, mt, pan, off, hedge)
        from binance_costs import side_frac
        fee = pd.Series({s: side_frac(s, "spot", mult) for s in held.columns})
        net = (held * ret.reindex(columns=held.columns).fillna(0)).sum(axis=1) - held.diff().abs().fillna(0).mul(fee, axis=1).sum(axis=1)
        net.index = pd.to_datetime(net.index).tz_localize(None) if net.index.tz is not None else net.index
        v = net[net.index >= lc.VAL_START]
        d = labecon.metrics(v, btc.set_axis(pd.to_datetime(btc.index).tz_localize(None) if btc.index.tz is not None else btc.index), n_tr)
        d["corr_ew18"] = round(float(np.corrcoef(v, ew.reindex(v.index).fillna(0))[0, 1]), 3)
        return d

    res: dict = {"name": a.name, "lab_trials": n_lab, "trials_used": n_tr, "holdout": "not read"}
    res["economics"] = {
        "base": econ(base), "cost_x2": econ(base, mult=2.0), "survivors_added": econ(ext), "btc_hedged": econ(base, hedge=True),
        "offsets": {str(o): econ(base, off=o) for o in range(h)}, "offsets_survivors": {str(o): econ(ext, off=o) for o in range(h)}}
    # BTC-relative long-short (variant): economics through a throw-away module
    rel_mod = SimpleNamespace(scores=lambda panel, **k: rel_scores(panel))
    rel_meta = {**meta, "portfolio": "long_short", "hedge_btc": True, "params": {"horizon": h}}
    has_btc = "BTCUSDT" in set(sc_base["symbol"])  # signals that already exclude BTC (market-neutral by design) have no BTC-relative variant
    if has_btc:
        res["economics"]["rel_btc_ls"] = econ(base, hedge=True, m=rel_mod, mt=rel_meta)

    # ---- verifier runs (alpha path), cached and parallel
    jobs = {
        "base_aum50k": (base, sc_base, 50_000), "base_aum500k": (base, sc_base, 500_000), "base_aum5m": (base, sc_base, 5_000_000),
        "survivors_aum50k": (ext, sc_ext, 50_000)}
    if has_btc:
        jobs["rel_btc_aum50k"] = (base, rel_scores(base), 50_000)
    for o in range(h):
        jobs[f"offset{o}_aum50k"] = (base, thin(sc_base, o), 50_000)
    with ThreadPoolExecutor(a.threads) as ex:
        futs = {k: ex.submit(cached, w, k, lambda k=k, v=v: alpha_run(w, k, v[0], v[1], h, v[2], n_tr, 1)) for k, v in jobs.items()}
        res["alpha"] = {k: f.result() for k, f in futs.items()}

    # ---- the basket as returns (certificate with an id) and the same rule per coin as a STRATEGY (full code-level verify)
    net = labecon.net_returns(a.name, cut)
    net.index = pd.to_datetime(net.index).tz_localize(None) if net.index.tz is not None else net.index
    net.rename_axis("date").to_csv(w / "basket_returns.csv", header=["return"])
    r = lc.mn("verify", "--returns", str(w / "basket_returns.csv"), "--n-strategies", str(n_tr), "--periods-per-year", str(lc.PPY), "--out", str(w / "basket.cert.json"))
    cert = json.loads((w / "basket.cert.json").read_text())
    res["basket_returns_cert"] = lc.summarize(cert) | {"checks": None}
    if a.name != "r2_channel_basket":  # per-coin code-level verify is specific to the channel rule
        out = lc.RES / f"{a.name}_robustness.json"
        out.write_text(json.dumps(res, indent=1, default=str))
        print(f"written {out}")
        return 0
    sig = w / "chan_signal.py"
    sig.write_text('import numpy as np\n\n\ndef signal(df, window=55):\n    c = df["close"]\n    hi, lo = c.shift(1).rolling(window).max(), c.shift(1).rolling(window).min()\n'
                   '    return (((c - lo) / (hi - lo) - 0.5) > 0).astype(float).to_numpy()\n')

    def per_coin(sym: str) -> dict:
        p = w / f"ohlcv_{sym}.parquet"
        base[sym].to_parquet(p)
        out = w / f"verify_{sym}.cert.json"
        lc.mn("verify", "--ohlcv", str(p), "--strategy", str(sig), "--commission-bps", "10", "--slippage-bps", "5", "--periods-per-year", "365", "--n-trials", str(n_tr),
              "--ledger", str(lc.LAB_LEDGER), "--out", str(out), threads=1)
        if not out.exists():
            return {"error": "no certificate"}
        c = json.loads(out.read_text())
        s = lc.summarize(c)
        return {k: s[k] for k in ("verdict", "certificate_id", "arl", "sharpe", "deflated_sharpe", "timing_p")} | {"failed": [x["id"] for x in s["checks"] if x["status"] == "fail"]}

    with ThreadPoolExecutor(a.threads) as ex:
        futs = {s: ex.submit(cached, w, f"coin_{s}", lambda s=s: per_coin(s)) for s in base}
        res["per_coin_verify"] = {s: f.result() for s, f in futs.items()}
    out = lc.RES / f"{a.name}_robustness.json"
    out.write_text(json.dumps(res, indent=1, default=str))
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(lc.STRATS / "_common"))
    raise SystemExit(main())
