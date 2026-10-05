"""Run ``monte-neo doctor`` and ``monte-neo discover`` on several real market files and write one summary.

python scripts/real_markets_run.py --out real-run data/real/btc_1h.csv data/real/eth_1h.csv data/real/spy_1d.csv

For every file: the data doctor, then discover with the same settings (seed, budget, 39 shuffled markets, lockbox 20 %),
costs by market class (crypto 10 bp, ETF 2 bp per side). Writes ``<out>/<name>/`` as ``monte-neo discover`` does and
``<out>/SUMMARY.md``. A search that names nothing is an expected result on real markets.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def cost_for(name: str) -> float:
    return 2.0 if any(k in name.lower() for k in ("spy", "qqq", "gld", "tlt", "etf", "1d")) else 10.0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("files", nargs="+")
    p.add_argument("--out", default="real-run")
    p.add_argument("--budget", type=int, default=3000)
    p.add_argument("--null-runs", type=int, default=39)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--evolve", type=int, default=2)
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for f in a.files:
        name = Path(f).stem
        doc = subprocess.run([sys.executable, "-m", "monte_neo", "doctor", f], capture_output=True, text=True, check=False)
        run = subprocess.run(
            [sys.executable, "-m", "monte_neo", "discover", "--ohlcv", f, "--out", str(out / name), "--budget", str(a.budget),
             "--null-runs", str(a.null_runs), "--seed", str(a.seed), "--evolve", str(a.evolve), "--cost-bps", str(cost_for(name))],
            capture_output=True, text=True, check=False,
        )
        res_file = out / name / "result.json"
        if run.returncode in (0, 1) and res_file.exists():
            r = json.loads(res_file.read_text(encoding="utf-8"))
            rows.append((name, doc.returncode, r["found"], r["search"]["candidates"], r["search"]["effective_trials"], r["search"]["best_sharpe"],
                         r["search"]["p_search_null"], r["lockbox"]["sharpe"], r["certificate"]["verdict"], "; ".join(r["reasons"])[:200]))
        else:
            rows.append((name, doc.returncode, None, 0, 0, None, None, None, "ERROR", (run.stderr or run.stdout).strip()[:200]))
    lines = ["# Discover on real markets", "", "| Market | Doctor | Found | Candidates | Effective trials | Best Sharpe | p (search null) | Lockbox Sharpe | Verdict | Why not |", "|---|---|---|---|---|---|---|---|---|---|"]
    for n, d, found, c, e, bs, pn, ls, v, why in rows:
        lines.append(f"| {n} | {'errors' if d == 2 else 'ok'} | {found} | {c} | {e} | {bs} | {pn} | {ls} | {v} | {why} |")
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
