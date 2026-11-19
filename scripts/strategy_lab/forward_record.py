"""Strategy Lab forward record: signals and HYPOTHETICAL positions of a FROZEN candidate list on public data, from 2026-11-10 on.

This is NOT a paper-trading account and NOT a testnet: no orders, no keys, no exchange account. Only public prices/funding are read and
a hash-chained journal is appended (strategy_lab/forward/journal.jsonl). Each line holds the day's inputs digest, signals, target and carried
weights, and the gross hypothetical return of the previous positions (no costs; costs are applied downstream from the recorded turnover).
Not investment advice.

  python scripts/strategy_lab/forward_record.py freeze      # once, BEFORE the first record day; commit forward/frozen.json
  python scripts/strategy_lab/forward_record.py run         # idempotent: records every missing day up to the last complete one (resume after any gap)
  python scripts/strategy_lab/forward_record.py run --dry-run   # synthetic prices, scratch folder, nothing is written to forward/
  python scripts/strategy_lab/forward_record.py status      # chain check + last day

Recording rules (fixed at freeze time, written in frozen.json):
 * Day D is recorded from data up to and including the complete UTC daily bar D (run it on D+1 or later; a record made later than D+1 is flagged late).
 * Crypto alpha candidates: the strategy's own scores(); long the top third, short the bottom third of the point-in-time eligible coins, equal weight,
   gross 1 (0.5 per side), rebalanced every 3 days counted from the start day. The BTC hedge of the Lab alpha path is not modelled here.
 * Funding comes from OKX (a proxy for Binance funding, which is not reachable from here); perp volume from the Binance bulk archive.
 * Carry E_pit: BTC..SOL pool of 12, weekly decisions counted from the start day, hold state with the frozen enter/exit thresholds on the 30-day mean daily funding,
   universe = top 2 pool coins by perp quote volume over the 30 bars before the decision date, weight 1/3 x hold x in_universe (spot long + perp short, funding earned).
 * ETF candidates: weights from etf_ideas on data up to D, flagged rebalance on the last weekday of a month (exchange holidays are not modelled), leverage cap 1.
 * Warm-up history (crypto from 2025-10-01) is read only as input for the windows; no performance is computed on any date before the start day.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import etf_ideas as ei  # noqa: E402

START = pd.Timestamp("2026-11-10")
FETCH_FROM = pd.Timestamp("2025-10-01")  # warm-up for the 365-day windows only
def SHORT_FROM() -> pd.Timestamp:
    return min(pd.Timestamp(datetime.now(UTC).date()) - pd.Timedelta(days=50), START - pd.Timedelta(days=50))


FWD = ROOT / "strategy_lab" / "forward"
CACHE = FWD / "cache"
CRYPTO = ["r4_b4_2_18bcb0", "r4_b3_1_68ed02", "r4_b2_1_1d13a6", "r4_b1_5_ff0569"]
ETF = ["etf_risk_parity", "etf_bond_trend_carry", "etf_tsmom_voltarget"]
CARRY = {"id": "carry_E_pit", "L": 30, "enter": 0.0002, "exit": 0.00005, "R": 7, "w": 1 / 3, "top_n": 2, "lookback": 30,
         "pool": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOGEUSDT", "DOTUSDT", "AVAXUSDT", "ATOMUSDT", "SOLUSDT"]}
UA = {"User-Agent": "Mozilla/5.0 (research script; monte-neo strategy lab)"}
STRAT = ROOT / "examples" / "strategies"


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), default=str)


# ---------------------------------------------------------------- freeze
def frozen_spec() -> dict:
    cand = {}
    for n in CRYPTO:
        cand[n] = {"kind": "crypto_alpha", "horizon_days": 3, "files": {f"examples/strategies/{n}/strategy.py": sha(STRAT / n / "strategy.py")}}
    cand[CARRY["id"]] = {"kind": "carry", "params": CARRY}
    for n in ETF:
        cand[n] = {"kind": "etf", "params": ei.IDEAS[n]["params"]}
    common = {f"examples/strategies/_common/{f}": sha(STRAT / "_common" / f) for f in ("signals.py", "wide_universe.json")}
    code = {f"scripts/strategy_lab/{f}": sha(HERE / f) for f in ("forward_record.py", "etf_ideas.py")}
    return {"start": str(START.date()), "candidates": cand, "common_files": common, "code_files": code,
            "note": "Frozen before the first record day. Any change of these hashes makes `run` refuse. Not investment advice; no trading."}


def check_frozen() -> dict:
    p = FWD / "frozen.json"
    if not p.exists():
        raise SystemExit("not frozen: run `forward_record.py freeze` and commit strategy_lab/forward/frozen.json first")
    spec = json.loads(p.read_text())
    now = frozen_spec()
    if canon({k: v for k, v in now.items() if k != "note"}) != canon({k: v for k, v in spec.items() if k != "note"}):
        raise SystemExit("frozen candidates, parameters or code changed since the freeze: refusing to record")
    spec["_sha"] = sha(p)
    return spec


# ---------------------------------------------------------------- data
def http_json(url: str, tries: int = 6):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            if "HTTP Error 400" in str(e) or "HTTP Error 404" in str(e):
                return None
            time.sleep(min(30, 2 ** (k + 1)))
    return None


def ms(ts: pd.Timestamp) -> int:
    return int(ts.tz_localize("UTC").timestamp() * 1000) if ts.tzinfo is None else int(ts.timestamp() * 1000)


def klines(base: str, sym: str, since: pd.Timestamp) -> pd.DataFrame | None:
    path = "api/v3/klines"
    rows, t = [], since
    while True:
        j = http_json(f"{base}/{path}?symbol={sym}&interval=1d&startTime={ms(t)}&limit=1000")
        if not j:
            break
        rows += j
        if len(j) < 1000:
            break
        t = pd.Timestamp(j[-1][0], unit="ms") + pd.Timedelta(days=1)
    if not rows:
        return None
    df = pd.DataFrame(rows).iloc[:, :8]
    df.columns = ["t", "open", "high", "low", "close", "volume", "ct", "qv"]
    df["timestamp"] = pd.to_datetime(df["t"], unit="ms")
    return df[["timestamp", "close", "volume", "qv"]].astype({"close": float, "volume": float, "qv": float})


def perp_qv(sym: str, since: pd.Timestamp) -> pd.DataFrame | None:
    """USD-M perpetual daily klines from the public bulk archive (fapi.binance.com is geo-blocked here); a day that is not published yet is skipped."""
    import io
    import zipfile
    rows = []
    for d in pd.date_range(since.normalize(), pd.Timestamp(datetime.now(UTC).date()) - pd.Timedelta(days=1)):
        url = f"https://data.binance.vision/data/futures/um/daily/klines/{sym}/1d/{sym}-1d-{d.date()}.zip"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                raw = zipfile.ZipFile(io.BytesIO(r.read())).read(f"{sym}-1d-{d.date()}.csv").decode().strip().splitlines()[-1].split(",")
            rows.append({"timestamp": d, "close": float(raw[4]), "volume": float(raw[5]), "qv": float(raw[7])})
        except Exception:  # noqa: BLE001 - 404 = not published yet
            continue
    return pd.DataFrame(rows) if rows else None


def funding(sym: str, since: pd.Timestamp) -> pd.Series | None:
    """Daily sum of perpetual funding. SOURCE: OKX public funding history (a PROXY of Binance funding: fapi.binance.com is geo-blocked from the
    owner's location and the Binance bulk archive publishes funding only per finished month). Recorded as such in every journal line."""
    inst = sym.replace("USDT", "-USDT-SWAP")
    rows, after = [], ""
    while True:
        j = http_json(f"https://www.okx.com/api/v5/public/funding-rate-history?instId={inst}&limit=100{after}")
        if not j or not j.get("data"):
            break
        rows += j["data"]
        oldest = int(j["data"][-1]["fundingTime"])
        if pd.Timestamp(oldest, unit="ms") < since:
            break
        after = f"&after={oldest}"
        time.sleep(0.15)
    if not rows:
        return None
    s = pd.Series([float(r["realizedRate"] or r["fundingRate"]) for r in rows], index=pd.to_datetime([int(r["fundingTime"]) for r in rows], unit="ms"))
    return s.sort_index().loc[since:].resample("1D").sum()


def cached(name: str, fetch, since_default: pd.Timestamp, refresh_days: int = 4):
    """Incremental parquet cache: re-reads the last few days, appends, de-duplicates."""
    p = CACHE / f"{name}.parquet"
    old = pd.read_parquet(p) if p.exists() else None
    since = since_default if old is None or len(old) == 0 else max(since_default, pd.Timestamp(old.index.max() if "timestamp" not in old else old["timestamp"].max()) - pd.Timedelta(days=refresh_days))
    new = fetch(since)
    if new is None:
        return old
    if isinstance(new, pd.Series):
        new = new.rename("funding").to_frame()
        new.index.name = "timestamp"
        new = new.reset_index()
    df = new if old is None else pd.concat([old, new])
    df = df.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p.with_suffix(".tmp"), index=False)
    os.replace(p.with_suffix(".tmp"), p)
    return df


def synth(sym: str, since) -> pd.DataFrame:
    rng = np.random.default_rng(abs(hash(sym)) % 2**32)
    idx = pd.date_range(since, pd.Timestamp.utcnow().tz_localize(None).normalize() - pd.Timedelta(days=1))
    px = 10 * np.exp(np.cumsum(rng.normal(0, 0.03, len(idx))))
    return pd.DataFrame({"timestamp": idx, "close": px, "adjclose": px, "volume": rng.uniform(1e5, 1e7, len(idx)), "qv": rng.uniform(1e6, 1e8, len(idx))})


class Data:
    def __init__(self, dry: bool):
        self.dry = dry
        self.spot: dict[str, pd.DataFrame] = {}
        self.perp: dict[str, pd.DataFrame] = {}
        self.fund: dict[str, pd.DataFrame] = {}
        self.etf_adj = self.etf_cls = None

    def update(self) -> None:
        uni = json.loads((STRAT / "_common" / "wide_universe.json").read_text())
        syms = sorted(set(uni) | set(CARRY["pool"]))

        def one_spot(s):
            return s, cached(f"spot_{s}", (lambda since: synth(s, since)) if self.dry else (lambda since: klines("https://data-api.binance.vision", s, since)), FETCH_FROM)

        with ThreadPoolExecutor(6) as ex:
            for s, df in ex.map(one_spot, syms[:40] if self.dry else syms):
                if df is not None and len(df):
                    self.spot[s] = df
        for s in CARRY["pool"]:
            self.perp[s] = cached(f"perp_{s}", (lambda since, s=s: synth(s, since)) if self.dry else (lambda since, s=s: perp_qv(s, since)), SHORT_FROM())
            self.fund[s] = cached(f"fund_{s}", (lambda since: pd.Series(0.0003, index=pd.date_range(since, pd.Timestamp.utcnow().tz_localize(None).normalize() - pd.Timedelta(days=1)))) if self.dry
                                  else (lambda since, s=s: funding(s, since)), SHORT_FROM())
        import etf_data as ed
        adj, cls = {}, {}
        for s in ei.UNIVERSE:
            df = ed.synthetic(s) if self.dry else ed.fetch_yahoo(s)
            df = df.set_index("timestamp")
            adj[s], cls[s] = df["adjclose"], df["close"]
        self.etf_adj, self.etf_cls = pd.DataFrame(adj), pd.DataFrame(cls)


# ---------------------------------------------------------------- signals
def crypto_entry(name: str, D: pd.Timestamp, data: Data, prev: dict | None) -> dict:
    import labcore as lc
    mod = lc.load_module(name)
    panel = {s: df[df["timestamp"] <= D][["timestamp", "close", "volume"]] for s, df in data.spot.items() if (df["timestamp"] <= D).sum() > 0}
    sc = mod.scores(panel)
    sc = sc[(pd.to_datetime(sc["timestamp"]) == D) & sc["score"].notna()].sort_values("score", ascending=False)
    n = len(sc)
    k = n // 3
    rebal = (D - START).days % 3 == 0
    prev_w = (prev or {}).get("weights", {})
    if rebal or prev is None:
        w = {r.symbol: 0.5 / k for r in sc.head(k).itertuples()} | {r.symbol: -0.5 / k for r in sc.tail(k).itertuples()} if k > 0 else {}
    else:
        w = prev_w
    px = {s: df.set_index("timestamp")["close"] for s, df in data.spot.items()}
    gross_ret = 0.0
    for s, wi in prev_w.items():
        if s in px and D in px[s].index and (D - pd.Timedelta(days=1)) in px[s].index:
            gross_ret += wi * (px[s][D] / px[s][D - pd.Timedelta(days=1)] - 1)
    turn = sum(abs(w.get(s, 0) - prev_w.get(s, 0)) for s in set(w) | set(prev_w))
    return {"rebalance": bool(rebal or prev is None), "eligible": n, "weights": {s: round(v, 6) for s, v in w.items()},
            "gross_ret_prev_positions": round(gross_ret, 8), "turnover": round(turn, 6),
            "inputs_digest": hashlib.sha256(canon(sc[["symbol", "score"]].round(10).values.tolist()).encode()).hexdigest()}


def carry_entry(D: pd.Timestamp, data: Data, prev: dict | None) -> dict:
    c = CARRY
    F = pd.DataFrame({s: data.fund[s].set_index("timestamp")["funding"] for s in c["pool"]}).sort_index()
    F = F[F.index <= D]
    mL = F.rolling(c["L"], min_periods=c["L"]).mean().iloc[-1] if len(F) else pd.Series(dtype=float)
    hold = dict((prev or {}).get("hold", {s: False for s in c["pool"]}))
    uni = list((prev or {}).get("universe", []))
    decide = (D - START).days % c["R"] == 0 or prev is None
    if decide:
        QV = pd.DataFrame({s: data.perp[s].set_index("timestamp")["qv"] for s in c["pool"]}).sort_index()
        win = QV[(QV.index < D) & (QV.index >= D - pd.Timedelta(days=c["lookback"]))]
        uni = list(win.sum().sort_values(ascending=False).head(c["top_n"]).index) if len(win) >= c["lookback"] - 2 else []
        for s in c["pool"]:
            m = mL.get(s, np.nan)
            if hold[s]:
                hold[s] = bool(np.isfinite(m) and m > c["exit"])
            else:
                hold[s] = bool(np.isfinite(m) and m > c["enter"])
    w = {s: round(c["w"], 6) for s in c["pool"] if hold[s] and s in uni}
    pw = (prev or {}).get("weights", {})
    fday = {s: float(F[s].get(D, np.nan)) for s in pw if s in F}
    accrual = sum(wi * (fday[s] if np.isfinite(fday.get(s, np.nan)) else 0.0) for s, wi in pw.items())
    return {"decision_day": bool(decide), "mean_funding_30d": {s: (None if not np.isfinite(mL.get(s, np.nan)) else round(float(mL[s]), 8)) for s in c["pool"]},
            "hold": hold, "universe": uni, "weights": w, "funding_accrual_prev_positions": round(accrual, 8),
            "turnover": round(sum(abs(w.get(s, 0) - pw.get(s, 0)) for s in set(w) | set(pw)), 6),
            "pnl_note": "funding only; basis, fees, margin and capital cost are applied downstream"}


def etf_entry(name: str, D: pd.Timestamp, data: Data, prev: dict | None) -> dict:
    adj, cls = data.etf_adj[data.etf_adj.index <= D], data.etf_cls[data.etf_cls.index <= D]
    asof = adj.index.max()
    w_raw = ei.IDEAS[name]["fn"](adj, cls, **ei.IDEAS[name]["params"]).iloc[-1].fillna(0.0)
    rebal = bool((D + pd.offsets.BDay(1)).month != D.month) or prev is None
    pw = (prev or {}).get("weights", {})
    if rebal:
        g = float(w_raw.abs().sum())
        w = (w_raw / max(g, 1.0))
        w = {s: round(float(v), 6) for s, v in w.items() if abs(v) > 1e-9}
    else:
        w = pw
    ret = adj.pct_change(fill_method=None).iloc[-1] if len(adj) > 1 and asof == D else pd.Series(dtype=float)
    gross = float(sum(wi * (ret.get(s, 0.0) if np.isfinite(ret.get(s, 0.0)) else 0.0) for s, wi in pw.items()))
    return {"asof_bar": str(asof.date()), "new_bar": bool(asof == D), "rebalance": rebal, "weights": w, "gross_ret_prev_positions": round(gross, 8),
            "turnover": round(sum(abs(w.get(s, 0) - pw.get(s, 0)) for s in set(w) | set(pw)), 6),
            "inputs_digest": hashlib.sha256(canon(adj.iloc[-1].round(6).to_dict()).encode()).hexdigest()}


# ---------------------------------------------------------------- journal
def read_journal(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def verify_chain(rows: list[dict]) -> bool:
    prev = "0" * 64
    for r in rows:
        body = {k: v for k, v in r.items() if k != "hash"}
        if r["prev_hash"] != prev or hashlib.sha256((prev + canon(body)).encode()).hexdigest() != r["hash"]:
            return False
        prev = r["hash"]
    return True


def cmd_freeze(a) -> int:
    FWD.mkdir(parents=True, exist_ok=True)
    p = FWD / "frozen.json"
    if p.exists():
        raise SystemExit("already frozen; the freeze is never rewritten")
    p.write_text(json.dumps(frozen_spec(), indent=1, sort_keys=True))
    print(f"wrote {p}; commit it before {START.date()}")
    return 0


def cmd_status(a) -> int:
    rows = read_journal(FWD / "journal.jsonl")
    print(f"records: {len(rows)}; chain {'OK' if verify_chain(rows) else 'BROKEN'}; last day: {rows[-1]['day'] if rows else '-'}; start {START.date()}")
    return 0


def cmd_run(a) -> int:
    global FWD, CACHE, START
    if a.dry_run:
        FWD = Path(tempfile.mkdtemp(prefix="fwd_dry_"))
        CACHE = FWD / "cache"
        frozen_sha = "dry-run"
    else:
        frozen_sha = check_frozen()["_sha"]
    FWD.mkdir(parents=True, exist_ok=True)
    jp = FWD / "journal.jsonl"
    with open(FWD / "run.lock", "w") as lk:
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("another instance is running")
            return 0
        rows = read_journal(jp)
        if not verify_chain(rows):
            raise SystemExit("journal hash chain is broken: not appending")
        last_complete = pd.Timestamp(datetime.now(UTC).date()) - pd.Timedelta(days=1)
        start = pd.Timestamp("2026-10-20") if a.dry_run else START  # dry run: pretend it started earlier
        START = start
        have = {r["day"] for r in rows}
        todo = [d for d in pd.date_range(start, last_complete) if str(d.date()) not in have]
        if not todo:
            print(f"up to date (last complete day {last_complete.date()})")
            return 0
        data = Data(a.dry_run)
        data.update()
        state = {}
        if rows:
            state = {k: v for k, v in rows[-1]["candidates"].items()}
        prev_hash = rows[-1]["hash"] if rows else "0" * 64
        names = CRYPTO + [CARRY["id"]] + ETF
        for D in todo:
            ents = {}
            for n in names:
                prev = state.get(n)
                ents[n] = carry_entry(D, data, prev) if n == CARRY["id"] else (etf_entry(n, D, data, prev) if n in ETF else crypto_entry(n, D, data, prev))
            state = ents
            body = {"day": str(D.date()), "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "late": bool(pd.Timestamp(datetime.now(UTC).date()) > D + pd.Timedelta(days=1)), "frozen_sha256": frozen_sha,
                    "n_spot_symbols": len(data.spot), "sources": {"spot": "data-api.binance.vision", "perp_volume": "data.binance.vision daily", "funding": "OKX public (proxy)", "etf": "Yahoo chart"}, "candidates": ents, "prev_hash": prev_hash}
            h = hashlib.sha256((prev_hash + canon(body)).encode()).hexdigest()
            with open(jp, "a") as f:
                f.write(canon({**body, "hash": h}) + "\n")
                f.flush()
                os.fsync(f.fileno())
            prev_hash = h
            print(f"recorded {D.date()} {h[:12]}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["freeze", "run", "status"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return {"freeze": cmd_freeze, "run": cmd_run, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
