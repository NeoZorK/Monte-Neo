"""Strategy Lab track 2: ETF daily series. Downloader (resumable, SHA-256 manifest) and loader that never reads past the cut.

Source: Yahoo chart API (close + adjusted close). The series are split at download time: ``etf_SYM_pre.parquet`` (<= 2020-12-31) and
``etf_SYM_sealed.parquet`` (2021+, holdout and forward). The loader opens the sealed files only with ``sealed=True``, which the holdout
stage may use for a frozen candidate. Series are git-ignored. Not investment advice; no keys, no trading.

  python scripts/strategy_lab/etf_data.py fetch [--dry-run]     # resume-safe; --refresh re-downloads
  python scripts/strategy_lab/etf_data.py status
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etf_ideas import UNIVERSE, VAL_END  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HOME = Path(os.environ["STRATEGY_LAB_HOME"]) if os.environ.get("STRATEGY_LAB_HOME") else ROOT / "strategy_lab"
OUT = Path(os.environ.get("LAB_ETF_DIR") or HOME / "data_etf")
UA = {"User-Agent": "Mozilla/5.0 (research script; monte-neo strategy lab)"}


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def fetch_yahoo(sym: str, tries: int = 6) -> pd.DataFrame:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1=0&period2={int(time.time()) + 86400}&interval=1d&events=div%2Csplit"
    last = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                j = json.load(r)
            res = j["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            adj = res["indicators"]["adjclose"][0]["adjclose"]
            df = pd.DataFrame({"timestamp": pd.to_datetime(res["timestamp"], unit="s").normalize(), "close": q["close"], "adjclose": adj,
                               "volume": q["volume"]}).dropna(subset=["close", "adjclose"])
            return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
        except Exception as e:  # noqa: BLE001 - retry on any network/parse error
            last = e
            time.sleep(min(60, 2 ** (k + 1)))
    raise RuntimeError(f"{sym}: {last}")


def synthetic(sym: str) -> pd.DataFrame:
    import numpy as np
    rng = np.random.default_rng(abs(hash(sym)) % 2**32)
    idx = pd.bdate_range("2005-01-03", "2023-06-30")
    px = 50 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(idx))))
    return pd.DataFrame({"timestamp": idx, "close": px, "adjclose": px * 1.0, "volume": 1e6})


def write_symbol(sym: str, df: pd.DataFrame) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    pre, sealed = df[df["timestamp"] <= VAL_END], df[df["timestamp"] > VAL_END]
    out = {}
    for tag, part in (("pre", pre), ("sealed", sealed)):
        p = OUT / f"etf_{sym}_{tag}.parquet"
        part.to_parquet(p.with_suffix(".tmp"), index=False)
        os.replace(p.with_suffix(".tmp"), p)
        out[tag] = {"rows": len(part), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    "first": str(part["timestamp"].min())[:10] if len(part) else None, "last": str(part["timestamp"].max())[:10] if len(part) else None}
    return out


def cmd_fetch(a) -> int:
    man_p = OUT / "manifest.json"
    man = json.loads(man_p.read_text()) if man_p.exists() else {}
    for i, sym in enumerate(UNIVERSE, 1):
        if sym in man and not a.refresh:
            print(f"[{i}/{len(UNIVERSE)}] {sym}: have it ({man[sym]['pre']['rows']}+{man[sym]['sealed']['rows']} rows)", flush=True)
            continue
        df = synthetic(sym) if a.dry_run else fetch_yahoo(sym)
        man[sym] = write_symbol(sym, df)
        _atomic(man_p, json.dumps(man, indent=1, sort_keys=True).encode())
        print(f"[{i}/{len(UNIVERSE)}] {sym}: pre {man[sym]['pre']['first']}..{man[sym]['pre']['last']} ({man[sym]['pre']['rows']} rows)", flush=True)
        time.sleep(0 if a.dry_run else 1.5)
    print("done" if len(man) == len(UNIVERSE) else "incomplete")
    return 0


def load_panel(upto: str, sealed: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(adjusted close, close) panels with rows <= upto. ``upto`` > 2020-12-31 needs sealed=True (holdout/forward only)."""
    cut = pd.Timestamp(upto)
    if cut > VAL_END and not sealed:
        raise PermissionError("the ETF holdout (2021+) is sealed: pass sealed=True only for a frozen candidate")
    adj, cls = {}, {}
    for sym in UNIVERSE:
        parts = []
        for tag in ("pre", "sealed") if sealed else ("pre",):
            p = OUT / f"etf_{sym}_{tag}.parquet"
            if p.exists():
                parts.append(pd.read_parquet(p))
        if not parts:
            continue
        df = pd.concat(parts).set_index("timestamp").sort_index()
        df = df[df.index <= cut]
        adj[sym], cls[sym] = df["adjclose"], df["close"]
    return pd.DataFrame(adj), pd.DataFrame(cls)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["fetch", "status"])
    ap.add_argument("--dry-run", action="store_true", help="synthetic series into a scratch folder")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    global OUT
    if a.dry_run:
        OUT = Path(tempfile.mkdtemp(prefix="etf_dry_"))
    if a.cmd == "status":
        m = json.loads((OUT / "manifest.json").read_text()) if (OUT / "manifest.json").exists() else {}
        print(f"{len(m)}/{len(UNIVERSE)} symbols; missing: {[s for s in UNIVERSE if s not in m]}")
        return 0
    return cmd_fetch(a)


if __name__ == "__main__":
    raise SystemExit(main())
