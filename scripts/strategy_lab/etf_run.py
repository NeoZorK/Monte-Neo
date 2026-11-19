"""Strategy Lab track 2: run the pre-registered ETF ideas on discovery and validation (holdout sealed) and verify them with Monte-Neo.

  python scripts/strategy_lab/etf_run.py            # all ideas, resumable per idea/slice (certificates in strategy_lab/work/etf)
  python scripts/strategy_lab/etf_run.py --dry-run  # synthetic panel in a scratch folder

n_trials = Lab-wide (all crypto variants + the 16 ETF grid points). Returns-only certificates: the ARL is what Monte-Neo can say about a
return series (see arl_scope). Not investment advice; nothing trades.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import etf_data  # noqa: E402
import etf_ideas as ei  # noqa: E402
import labcore as lc  # noqa: E402

PPY = ei.PPY
SLICES = {"disc": (None, ei.DISC_END), "val": (ei.DISC_END + pd.Timedelta(days=1), ei.VAL_END)}


def sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * np.sqrt(PPY)) if len(r) > 20 and r.std() > 0 else float("nan")


def beta_alpha_t(r: pd.Series, b: pd.Series) -> tuple[float, float]:
    d = pd.concat([r, b], axis=1).dropna()
    x, y = d.iloc[:, 1].to_numpy(), d.iloc[:, 0].to_numpy()
    X = np.column_stack([np.ones(len(x)), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ coef
    cov = np.linalg.inv(X.T @ X) * res.var(ddof=2)
    return float(coef[1]), float(coef[0] / np.sqrt(cov[0, 0]))


def cut(r: pd.Series, lo, hi) -> pd.Series:
    r = r[r.index <= hi]
    return r[r.index >= lo] if lo is not None else r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    if a.dry_run:
        tmp = Path(tempfile.mkdtemp(prefix="etf_run_dry_"))
        etf_data.OUT = tmp / "data"
        for s in ei.UNIVERSE:
            etf_data.write_symbol(s, etf_data.synthetic(s))
        out_dir = tmp / "out"
    else:
        out_dir = lc.WORK / "etf"
    out_dir.mkdir(parents=True, exist_ok=True)
    adj, cls = etf_data.load_panel(ei.VAL_END.strftime("%Y-%m-%d"))  # sealed=False: cannot read 2021+
    n_trials = lc.total_trials() if not a.dry_run else 150
    spy = adj["SPY"].pct_change(fill_method=None)
    rows = []
    for name, idea in ei.IDEAS.items():
        d = out_dir / name
        d.mkdir(exist_ok=True)
        rec_p = d / "record.json"
        if rec_p.exists():
            rows.append(json.loads(rec_p.read_text()))
            print(f"{name}: have it", flush=True)
            continue
        base = ei.backtest(name, adj, cls)
        x2 = ei.backtest(name, adj, cls, cost_bps=2 * ei.COST_BPS, borrow_bps=2 * ei.BORROW_BPS_YEAR)
        grid = {json.dumps(g): ei.backtest(name, adj, cls, params=g) for g in ei.combos(idea["grid"])}
        rec = {"idea": name, "ref": idea["ref"], "params": idea["params"], "n_trials": n_trials}
        for tag, (lo, hi) in SLICES.items():
            r, rb = cut(base, lo, hi), cut(spy, lo, hi)
            r.rename_axis("date").to_csv(d / f"returns_{tag}.csv", header=["return"])
            rb.dropna().rename_axis("date").to_csv(d / f"bench_{tag}.csv", header=["return"])
            if a.dry_run:
                cert = {}
            else:
                lc.mn("verify", "--returns", str(d / f"returns_{tag}.csv"), "--benchmark", str(d / f"bench_{tag}.csv"), "--n-strategies", str(n_trials),
                      "--periods-per-year", str(PPY), "--out", str(d / f"{tag}.cert.json"), threads=a.threads)
                cert = json.loads((d / f"{tag}.cert.json").read_text()) if (d / f"{tag}.cert.json").exists() else {}
            s = lc.summarize(cert) if cert else {}
            beta, at = beta_alpha_t(r, rb)
            yearly = {str(y): round(sharpe(g), 2) for y, g in r.groupby(r.index.year) if len(g) > 100}
            rec[tag] = {"bars": len(r), "first": str(r.index.min())[:10], "net_sharpe": round(sharpe(r), 3), "cost_x2_sharpe": round(sharpe(cut(x2, lo, hi)), 3),
                        "ann_return": round(float(r.mean() * PPY), 4), "ann_vol": round(float(r.std() * np.sqrt(PPY)), 4),
                        "max_dd": round(float(((1 + r).cumprod() / (1 + r).cumprod().cummax() - 1).min()), 4),
                        "beta_spy": round(beta, 3), "alpha_t_spy": round(at, 2), "sharpe_by_year": yearly,
                        "plateau_sharpes": {k: round(sharpe(cut(v, lo, hi)), 2) for k, v in grid.items()},
                        "cert": {k: s.get(k) for k in ("verdict", "arl", "arl_depth", "arl_headline", "deflated_sharpe", "certificate_id")}}
        rec_p.write_text(json.dumps(rec, indent=1))
        rows.append(rec)
        print(f"{name}: disc Sharpe {rec['disc']['net_sharpe']}, val Sharpe {rec['val']['net_sharpe']}", flush=True)
    lines = ["# ETF track: discovery (<=2014) and validation (2015-2020), holdout 2021+ sealed", "", f"n_trials = {n_trials} (all crypto variants + 16 ETF grid points). Not investment advice.", "",
             "| Idea | Slice | ARL/depth | Verdict | Net Sharpe | Costs x2 | DSR | Beta SPY | Alpha t | Max DD |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        for tag in SLICES:
            v, c = r[tag], r[tag]["cert"]
            lines.append(f"| {r['idea']} | {tag} | {c.get('arl')}/{c.get('arl_depth')} | {c.get('verdict')} | {v['net_sharpe']} | {v['cost_x2_sharpe']} | {c.get('deflated_sharpe')} | {v['beta_spy']} | {v['alpha_t_spy']} | {v['max_dd']} |")
    (out_dir / "etf_report.md").write_text("\n".join(lines) + "\n")
    if not a.dry_run:
        (lc.RES / "etf_summary.json").parent.mkdir(parents=True, exist_ok=True)
        (lc.RES / "etf_summary.json").write_text(json.dumps(rows, indent=1))
        (lc.RES / "etf_report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
