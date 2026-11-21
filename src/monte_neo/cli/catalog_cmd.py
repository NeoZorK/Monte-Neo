"""``monte-neo catalog``: label a strategy by the catalog rules (``catalog-rules/1``, provisional).

    monte-neo catalog classify spec.json [--positions pos.csv] [--prices close.csv] [--benchmark bench.csv] [--json]
    monte-neo catalog mask tm1:...            decode a type mask
    monte-neo catalog categories              list the 24 categories

``pos.csv`` and ``close.csv`` are wide tables: a first column of timestamps, one column per symbol.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from monte_neo.catalog import classify, decode, measure
from monte_neo.catalog.mask import rules


def _wide(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)
    try:
        df.index = pd.to_datetime(df.index, utc=True)
    except (ValueError, TypeError):
        pass
    return df


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="monte-neo catalog", description="Label a strategy by catalog-rules/1: category, tags, type mask.")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify", help="label one strategy specification (catalog-spec/1 JSON)")
    c.add_argument("spec")
    c.add_argument("--positions", help="wide CSV of signed positions (measured labels)")
    c.add_argument("--prices", help="wide CSV of close prices (returns, trend sign, size after a loss)")
    c.add_argument("--benchmark", help="CSV with a timestamp column and one benchmark return column (beta)")
    c.add_argument("--json", action="store_true", help="print the full record as JSON")
    mk = sub.add_parser("mask", help="decode a type mask")
    mk.add_argument("mask")
    sub.add_parser("categories", help="list the categories of catalog-rules/1")
    cp = sub.add_parser("compat", help="which venues and connectors can run this strategy (indicative, not a recommendation)")
    cp.add_argument("spec")
    cp.add_argument("--positions", help="wide CSV of signed positions (detects short selling and market neutrality)")
    cp.add_argument("--leverage", type=float, help="gross leverage the strategy needs (default from the spec, else 1)")
    cp.add_argument("--json", action="store_true")
    return p


def _print(rec: dict[str, Any]) -> None:
    print(f"{rec['type_tag']}  {rec['type_mask']}  ({rec['rules_version']}, provisional)")
    print(f"main {rec['main_category']} by {rec['main_rule']}; structure {rec['structure']}, holding {rec['holding']}, "
          f"breadth {rec['breadth']}, risk {rec['risk_shape']}, verifiable {rec['verifiable']}")
    for r in rec["rules_fired"]:
        print(f"  {r['rule']} {r['category']}: {r['why']}")
    if rec["flags"]:
        print("flags: " + ", ".join(rec["flags"]))
    print(f"catalog id prefix {rec['catalog_id_prefix']}  spec {rec['spec_hash'][:19]}")


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0) and 3
    try:
        if args.cmd == "categories":
            for code, name in rules()["categories"]:
                print(f"{code:4} {name}")
            return 0
        if args.cmd == "mask":
            print(json.dumps(decode(args.mask), indent=2))
            return 0
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        measured = None
        if args.cmd == "compat":
            from monte_neo.catalog.compat import compat

            m = measure(_wide(args.positions), None, bar_seconds=float(spec.get("bar_seconds", 86400))) if args.positions else None
            res = compat(spec, m, args.leverage)
            if args.json:
                print(json.dumps(res, indent=2, default=str))
                return 0
            req = res["requirements"]
            print(f"needs: {', '.join(req['asset_classes'])} via {', '.join(req['instruments'])}; short selling {'yes' if req['short'] else 'no'}"
                  f"; leverage {req['leverage']:g}x; intraday {'yes' if req['intraday'] else 'no'}")
            for r in res["venues"]:
                mark = "OK " if r["compatible"] else "-- "
                extra = f"taker ~{r['taker_bps']:g} bps, demo: {r['demo'] or 'none'}, connector: {r['connector']}" if r["compatible"] else "; ".join(r["why_not"])
                print(f"{mark}{r['name']:<32} {extra}")
            print(f"\n{res['note']}")
            return 0
        if args.positions:
            bench = None
            if args.benchmark:
                b = _wide(args.benchmark)
                bench = b.iloc[:, 0]
            measured = measure(_wide(args.positions), _wide(args.prices) if args.prices else None,
                               bar_seconds=float(spec.get("bar_seconds", 86400)), benchmark=bench)
        rec = classify(spec, measured)
    except (OSError, ValueError, KeyError) as exc:
        print(f"monte-neo catalog: {exc}", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(rec, indent=2, default=str))
    else:
        _print(rec)
    return 0


__all__ = ["main"]
