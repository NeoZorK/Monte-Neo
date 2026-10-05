"""``monte-neo discover`` — search for a causal indicator and verify the winner.

Writes strategy.py, result.json, search.jsonl (the journal of every candidate), certificate.json and report.html
into the output directory. Exit codes: 0 found, 1 nothing found, 3 usage or input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="monte-neo discover", description="Search for an indicator that survives the verifier.")
    p.add_argument("--ohlcv", required=True, help="OHLCV table (.csv / .parquet), at least 400 bars")
    p.add_argument("--out", default="discover-out", help="Output directory (default discover-out)")
    p.add_argument("--budget", type=int, default=2000, help="Candidates to try (default 2000)")
    p.add_argument("--seed", type=int, default=1, help="Seed of the search (default 1)")
    p.add_argument("--null-runs", type=int, default=39, help="Shuffled markets for the search null (default 39)")
    p.add_argument("--lockbox", type=float, default=0.2, help="Share of the last bars kept for one final look (default 0.2)")
    p.add_argument("--cost-bps", type=float, default=5.0, help="Round-trip cost per position change in bps (default 5)")
    p.add_argument("--side", choices=["long_short", "long_flat"], default="long_short")
    p.add_argument("--evolve", type=int, default=0, help="Generations of mutating the best candidates (default 0: random search only)")
    p.add_argument("--recheck", metavar="DIR", help="Re-run the search recorded in DIR/result.json on --ohlcv and compare the journal, the winner and the certificate id (exit 4 if different)")
    return p


def write_outputs(result: dict[str, Any], out: Path) -> None:
    """Write the files of a result into ``out`` (the journal goes to search.jsonl, not to result.json)."""
    from monte_neo.verify.report_html import render_html

    out.mkdir(parents=True, exist_ok=True)
    (out / "strategy.py").write_text(result["best"]["source"], encoding="utf-8")
    (out / "search.jsonl").write_text(result["journal"], encoding="utf-8")
    (out / "certificate.json").write_text(json.dumps(result["certificate"], indent=2, sort_keys=True, default=str), encoding="utf-8")
    (out / "report.html").write_text(render_html(result["certificate"]), encoding="utf-8")
    slim = {k: v for k, v in result.items() if k != "journal"}
    (out / "result.json").write_text(json.dumps(slim, indent=2, sort_keys=True, default=str), encoding="utf-8")


def recheck(df: Any, out: Path) -> int:
    """Run the recorded search again; the journal hash, the winner's source and the certificate id must all match."""
    from monte_neo.discover import Config, discover

    recorded = json.loads((out / "result.json").read_text(encoding="utf-8"))
    cfg = Config(**recorded["config"])
    again = discover(df, cfg)
    same = {
        "journal": again["journal_sha256"] == recorded["journal_sha256"],
        "winner": again["best"]["source"] == recorded["best"]["source"],
        "certificate": again["certificate"]["certificate_id"] == recorded["certificate"]["certificate_id"],
    }
    on_disk = (out / "search.jsonl")
    if on_disk.exists():
        import hashlib

        same["journal_file"] = hashlib.sha256(on_disk.read_bytes()).hexdigest() == recorded["journal_sha256"]
    print(json.dumps({"reproduced": all(same.values()), **same}, indent=2))
    return 0 if all(same.values()) else 4


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from monte_neo.discover import Config, discover
    from monte_neo.verify import load_ohlcv

    try:
        df = load_ohlcv(args.ohlcv)
        if args.recheck:
            return recheck(df, Path(args.recheck))
        cfg = Config(budget=args.budget, seed=args.seed, null_runs=args.null_runs, lockbox=args.lockbox, cost_bps=args.cost_bps, side=args.side, evolve=args.evolve)
        result = discover(df, cfg)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"discover: {exc}", file=sys.stderr)
        return 3
    write_outputs(result, Path(args.out))
    s = result["search"]
    print(f"{'FOUND' if result['found'] else 'NOTHING FOUND'}: {s['candidates']} candidates, {s['effective_trials']} effective trials, "
          f"p(search null) = {s['p_search_null']}, lockbox Sharpe {result['lockbox']['sharpe']}, verdict {result['certificate']['verdict']}")
    for r in result["reasons"]:
        print(f"  - {r}")
    print(f"Files in {args.out}/")
    return 0 if result["found"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
