"""Download public Binance klines and funding rates LOCALLY, with resume, a log, SHA-256 and a manifest.

    python scripts/strategy_lab/fetch_data.py --start 2017-08 --end 2026-10
    nohup python scripts/strategy_lab/fetch_data.py > strategy_lab/logs/fetch.out 2>&1 &

Raw zips and the processed tables stay in ``strategy_lab/data/`` (git-ignored). The series are not republished:
only metrics, verdicts and the hashes in ``manifest.json`` are. Safe to kill and restart at any time.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

BASE = "https://data.binance.vision/data"
# round 2: 18 liquid USDT coins (today's survivors: survivorship bias is declared in every card) and 12 perpetuals for carry/pairs
SPOT = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "LTCUSDT", "TRXUSDT", "LINKUSDT", "XLMUSDT", "ETCUSDT", "NEOUSDT", "ATOMUSDT",
        "DOGEUSDT", "BCHUSDT", "SOLUSDT", "DOTUSDT", "AVAXUSDT", "UNIUSDT"]
PERP = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOGEUSDT", "DOTUSDT", "AVAXUSDT", "ATOMUSDT"]
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "qv", "n", "tb", "tq", "ig"]
ROOT = Path(os.environ.get("LAB_DATA_DIR") or os.environ.get("STRATEGY_LAB_HOME") or Path(__file__).resolve().parents[2] / "strategy_lab") / "data"


def months(start: str, end: str) -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(start, end, freq="M")]


def jobs(start: str, end: str, spot: list[str], perp: list[str], avail: dict | None = None) -> list[tuple[str, str]]:
    """(kind, relative url path) for every monthly file; `avail` = {symbol: [months that exist]} skips the 404s."""
    out = []
    for m in months(start, end):
        out += [("spot", f"spot/monthly/klines/{s}/1d/{s}-1d-{m}.zip") for s in spot if avail is None or m in avail.get(s, [])]
        out += [("perp", f"futures/um/monthly/klines/{s}/1d/{s}-1d-{m}.zip") for s in perp]
        out += [("fund", f"futures/um/monthly/fundingRate/{s}/{s}-fundingRate-{m}.zip") for s in perp]
    return out


def get(url: str, tries: int = 8) -> bytes | None:
    """Download with capped exponential backoff (2, 4, ... 60 s); None on 404 (month not published / symbol not listed yet)."""
    err: Exception | None = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = e
        except Exception as e:  # network cut: back off and retry
            err = e
        time.sleep(min(60, 2 ** (k + 1)))
    raise RuntimeError(f"{url}: {err}")


def valid_zip(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as z:
            return z.testzip() is None
    except (zipfile.BadZipFile, OSError):
        return False


def fetch_one(rel: str, raw: Path, known: dict[str, str]) -> dict:
    dest = raw / rel
    if dest.exists():  # resume: a cached file is reused only if it is a whole zip and matches the manifest hash
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        if valid_zip(dest) and known.get(rel, sha) == sha:
            return {"rel": rel, "status": "cached", "sha256": sha}
        dest.unlink()  # truncated or altered: download again
    try:
        blob = get(f"{BASE}/{rel}")
        if blob is None:
            return {"rel": rel, "status": "missing"}
        sha = hashlib.sha256(blob).hexdigest()
        chk = get(f"{BASE}/{rel}.CHECKSUM")
    except RuntimeError as e:  # network is down for good: report, the next run continues from here
        return {"rel": rel, "status": "error", "error": str(e)[:200]}
    if chk is not None and chk.decode().split()[0].lower() != sha:
        return {"rel": rel, "status": "checksum_mismatch"}
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(blob)
    tmp.replace(dest)
    return {"rel": rel, "status": "ok", "sha256": sha}


def read_zip(path: Path, funding: bool) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as z:
        raw = z.read(z.namelist()[0]).decode()
    head = raw.split("\n", 1)[0]
    if funding:
        df = pd.read_csv(io.StringIO(raw), header=0 if "calc_time" in head else None)
        df = df.iloc[:, :3]
        df.columns = ["time", "interval", "rate"]
        df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="ms", utc=True)
        return df[["time", "rate"]]
    df = pd.read_csv(io.StringIO(raw), header=0 if head.startswith("open_time") else None, names=None if head.startswith("open_time") else COLS)
    t = df["open_time"].astype("int64")
    t = t.where(t < 10**14, t // 1000)  # newer spot files use microseconds
    df["timestamp"] = pd.to_datetime(t, unit="ms", utc=True)
    return df[["timestamp", "open", "high", "low", "close", "volume"]].astype({c: "float64" for c in ["open", "high", "low", "close", "volume"]})


def build(raw: Path, out: Path, spot: list[str], perp: list[str]) -> dict:
    """Concatenate monthly files into one daily parquet per series."""
    out.mkdir(parents=True, exist_ok=True)
    info = {}
    for kind, syms, sub in (("spot", spot, "spot/monthly/klines"), ("perp", perp, "futures/um/monthly/klines"), ("fund", perp, "futures/um/monthly/fundingRate")):
        for s in syms:
            files = sorted((raw / sub / s).rglob("*.zip"))
            if not files:
                continue
            df = pd.concat([read_zip(f, kind == "fund") for f in files])
            if kind == "fund":  # daily sum of funding rates (fraction of notional per day, paid by longs when positive)
                df = df.set_index("time")["rate"].astype(float).resample("1D").sum().rename("funding").to_frame()
                df.index.name = "timestamp"
                df = df.reset_index()
            else:
                df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
            p = out / f"{kind}_{s}_1d.parquet"
            df.to_parquet(p)
            info[p.name] = {"rows": len(df), "first": str(df["timestamp"].iloc[0].date()), "last": str(df["timestamp"].iloc[-1].date()),
                            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    return info


def write_json(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2017-08")
    ap.add_argument("--end", default="2026-10")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--months-file", type=Path, help="JSON {symbol: [YYYY-MM, ...]} of files that exist (skips 404 probes)")
    ap.add_argument("--threads", type=int, default=4, help="parallel downloads (default 4)")
    ap.add_argument("--spot", default=",".join(SPOT), help="comma separated spot symbols")
    ap.add_argument("--perp", default=",".join(PERP), help="comma separated perpetual symbols")
    a = ap.parse_args()
    spot, perp = [x for x in a.spot.split(",") if x], [x for x in a.perp.split(",") if x]
    raw, out = a.root / "raw", a.root / "processed"
    (a.root / "logs").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=a.root / "logs" / "fetch.log", level=logging.INFO, format="%(asctime)s %(message)s")
    todo = jobs(a.start, a.end, spot, perp, json.loads(a.months_file.read_text()) if a.months_file else None)
    t0, done, stat = time.time(), 0, {}
    manifest_p, prog_p = a.root / "manifest.json", a.root / "progress.json"
    files: dict[str, str] = json.loads(manifest_p.read_text()).get("files", {}) if manifest_p.exists() else {}
    known = dict(files)
    with ThreadPoolExecutor(a.threads) as ex:
        futs = [ex.submit(fetch_one, rel, raw, known) for _, rel in todo]
        for f in as_completed(futs):
            r = f.result()
            done += 1
            stat[r["status"]] = stat.get(r["status"], 0) + 1
            logging.info("%s %s %s", r["status"], r["rel"], r.get("error", ""))
            if "sha256" in r:
                files[r["rel"]] = r["sha256"]
            eta = (time.time() - t0) / done * (len(todo) - done)
            bar = "#" * (30 * done // len(todo))
            sys.stdout.write(f"\r[{bar:<30}] {done}/{len(todo)} ETA {eta:4.0f}s {stat}   ")
            sys.stdout.flush()
            if done % 25 == 0 or done == len(todo):  # progress for lab.py and a partial manifest for the next run
                write_json(prog_p, {"done": done, "total": len(todo), "stat": stat, "t0": t0, "updated": time.time()})
                write_json(manifest_p, {"source": BASE, "range": [a.start, a.end], "complete": False, "files": dict(sorted(files.items()))})
    print()
    bad, err = stat.get("checksum_mismatch", 0), stat.get("error", 0)
    series = build(raw, out, spot, perp)
    complete = not bad and not err
    write_json(manifest_p, {"source": BASE, "range": [a.start, a.end], "complete": complete, "files": dict(sorted(files.items())), "series": series})
    print(f"series: {len(series)}; checksum mismatches: {bad}; network errors: {err}; manifest: {manifest_p}")
    return 1 if bad else (2 if err else 0)


if __name__ == "__main__":
    raise SystemExit(main())
