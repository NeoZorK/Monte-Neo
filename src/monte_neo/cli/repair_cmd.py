"""``monte-neo repair`` — repair a strategy's defects without overfitting, or say why it cannot be repaired.

Exit codes: 0 repaired, 1 repaired but no edge left, 2 not repairable, 3 input error, 4 nothing to repair.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from rich.console import Console

from monte_neo import disclaimer

EXIT = {"REPAIRED": 0, "REPAIRED_NO_EDGE": 1, "NOT_REPAIRABLE": 2, "NOTHING_TO_REPAIR": 4}
STYLE = {"REPAIRED": "bold green", "REPAIRED_NO_EDGE": "bold yellow", "NOT_REPAIRABLE": "bold red", "NOTHING_TO_REPAIR": "bold"}


def build_parser() -> argparse.ArgumentParser:
    """The ``monte-neo repair`` options."""
    p = argparse.ArgumentParser(prog="monte-neo repair", description="Repair defects without overfitting; never touches the original file.")
    p.add_argument("--ohlcv", help="Prices (.csv / .parquet), as for verify")
    p.add_argument("--strategy", help="Strategy file 'path.py[:func]'")
    p.add_argument("--out", default="repair", help="Folder for strategy.repaired.py, repair.diff, certificate.json, repair-report.json/html")
    p.add_argument("--commission-bps", type=float, default=5.0)
    p.add_argument("--slippage-bps", type=float, default=5.0)
    p.add_argument("--n-trials", type=int, default=None, help="Variants tried before the repair (its candidates are added)")
    p.add_argument("--budget", type=int, default=24, help="At most this many candidate repairs (default 24)")
    p.add_argument("--dev-fraction", type=float, default=0.7, help="History used to choose; the rest is the lockbox, opened once")
    p.add_argument("--rebalance-every", type=int, default=None, help="The strategy rebalances every N bars: also try staggered tranches")
    p.add_argument("--explain", metavar="CERT", help="Explain the findings of a certificate JSON in plain words, with next actions, and exit (detect -> explain)")
    p.add_argument("--preview", metavar="FINDING", help="Try the automatic fix of one finding (F01 ...) and show before and after; the fix pays one trial; needs --ohlcv and --strategy")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--demo", action="store_true", help="Three strategies, three honest outcomes (writes into --out)")
    return p


def _print(name: str, rep: dict[str, Any], console: Console) -> None:
    o = rep["outcome"]
    console.print(f"[bold]{name}[/]: [{STYLE[o]}]{o}[/] — {rep['headline']}")
    orig = rep["original"]
    console.print(f"  before: {orig['verdict']}, net {orig['total_return']:+.1%}" if orig.get("total_return") is not None else f"  before: {orig['verdict']}")
    for c in rep["corrections"]:
        console.print(f"  correction {c['id']} {c.get('rule')}: {c.get('why')}")
    if rep.get("chosen"):
        console.print(f"  chosen on the first part of the history: {rep['chosen']['id']} {rep['chosen']['steps']} ({rep['chosen']['why']})")
    if rep.get("dev"):
        console.print(f"  defects on the development part: {rep['dev']['baseline_defects']} -> {rep['dev']['chosen_defects']}; trials counted: {rep['dev']['trials']}")
    if rep.get("lockbox"):
        lock = rep["lockbox"]
        console.print(f"  lockbox (opened once, from {lock['from'][:10]}): {lock['verdict']}, net {lock['total_return']:+.1%}")
    for b in rep["not_repairable"]:
        console.print(f"  [red]needs you:[/] {b}")


def _explain(args: argparse.Namespace, console: Console) -> int:
    from monte_neo.repair import explain

    try:
        cert = json.loads(open(args.explain, encoding="utf-8").read())
        found = explain(cert)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        console.print(f"[red]cannot explain: {exc}[/]")
        return 3
    if args.format == "json":
        print(json.dumps(found, indent=2))
        return 0
    if not found:
        console.print("No failed or warned check matches a known finding.")
    for f in found:
        console.print(f"[bold]{f['finding']} {f['title']}[/] ({', '.join(c['id'] for c in f['checks'])})", highlight=False)
        console.print(f"  why: {f['why']}", highlight=False)
        for a in f["next_actions"]:
            console.print(f"  -> {a}", highlight=False)
        console.print(f"  fix: {f['fix']}" + (f" (try: monte-neo repair --preview {f['finding']} ...)" if f["auto"] else " (only you can do it)"), highlight=False)
    console.print(f"[dim]{disclaimer.SHORT}[/]")
    return 0


def _preview(args: argparse.Namespace, console: Console) -> int:
    from monte_neo.repair import preview_fix
    from monte_neo.verify import load_ohlcv, model_from_costs
    from monte_neo.verify.market import bar_count

    if not (args.ohlcv and args.strategy):
        console.print("[red]--preview needs --ohlcv and --strategy[/]")
        return 3
    try:
        df = load_ohlcv(args.ohlcv)
        model = model_from_costs(commission_bps=args.commission_bps, slippage_bps=args.slippage_bps, n_bars=bar_count(df))
        res = preview_fix(args.preview, df, args.strategy, model=model, n_trials=args.n_trials)
    except (OSError, ValueError, SyntaxError, AttributeError) as exc:
        console.print(f"[red]preview failed: {exc}[/]")
        return 3
    if args.format == "json":
        print(json.dumps(res, indent=2, default=str))
        return 0
    if not res["applied"]:
        console.print(f"{res['finding']}: not applied: {res['reason']}", highlight=False)
        return 4
    console.print(res["diff"], markup=False, highlight=False)
    b, a = res["before"], res["after"]
    console.print(f"before: {b['verdict']} failed {b['failed']} trials {res['trials']['before']}", highlight=False)
    console.print(f"after:  {a['verdict']} failed {a['failed']} trials {res['trials']['after']}", highlight=False)
    console.print(f"[dim]{res['note']}[/]")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run ``monte-neo repair``."""
    from monte_neo.repair import repair_strategy
    from monte_neo.repair.report import write_html

    try:
        args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return 3 if exc.code == 2 else int(exc.code or 0)
    console = Console()
    if args.explain:
        return _explain(args, console)
    if args.preview:
        return _preview(args, console)
    try:
        if args.demo:
            from monte_neo.repair.demo import run_demo

            results = run_demo(args.out)
        elif args.ohlcv and args.strategy:
            from monte_neo.verify import load_ohlcv, model_from_costs
            from monte_neo.verify.market import bar_count

            df = load_ohlcv(args.ohlcv)
            model = model_from_costs(commission_bps=args.commission_bps, slippage_bps=args.slippage_bps, n_bars=bar_count(df))
            rep = repair_strategy(df, args.strategy, out_dir=args.out, model=model, n_trials=args.n_trials, budget=args.budget,
                                  dev_fraction=args.dev_fraction, rebalance_every=args.rebalance_every)
            results = [(args.strategy, rep)]
        else:
            console.print("[red]repair needs --ohlcv and --strategy, or --demo[/]")
            return 3
    except (OSError, ValueError, SyntaxError, AttributeError) as exc:
        console.print(f"[red]repair failed: {exc}[/]")
        return 3
    for name, rep in results:
        write_html(rep, args.out if not args.demo else f"{args.out}/{name}")
        if args.format == "json":
            print(json.dumps(rep, indent=2, default=str))
        else:
            _print(name, rep, console)
    console.print(f"[dim]{disclaimer.SHORT}[/]")
    return EXIT[results[-1][1]["outcome"]] if not args.demo else 0


__all__ = ["main"]
