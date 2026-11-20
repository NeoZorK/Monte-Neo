"""``monte-neo readiness``: the Alpha Readiness Level and its depth for the evidence given.

The Alpha Readiness Level (ARL) was devised by Rostyslav Shcherbyna, author of Monte-Neo; it is modelled on the idea of a
technology readiness level and is a Monte-Neo scale, not an industry standard. The rules are in ``arl_rules_v1.json``.

Exit codes: 0 printed, 3 input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="monte-neo readiness", description="ARL level and depth for a certificate, alpha report, live report and sealed holdout.")
    p.add_argument("--certificate", help="strategy-verdict/1 certificate (JSON)")
    p.add_argument("--alpha", help="alpha-report/1 (JSON)")
    p.add_argument("--live", help="live-monitor/1 (JSON)")
    p.add_argument("--holdout", help="sealed-holdout file (.monte-neo/sealed_holdout.jsonl)")
    p.add_argument("--n-trials", type=int, help="every variant tried in the whole project; levels 4-6 are computed with at least this many")
    p.add_argument("--rules-version", help="compute with this recorded rules version (default: current)")
    p.add_argument("--format", choices=("text", "json"), default="text")
    p.add_argument("--sync-docs", nargs="+", metavar="PAGE", help="regenerate the ARL tables in these documentation pages from the rules file and exit")
    return p


def _load(path: str | None) -> dict[str, Any] | None:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def main(argv: list[str] | None = None) -> int:
    """Run ``monte-neo readiness``; returns the exit code."""
    console = Console()
    try:
        args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return 3 if exc.code == 2 else int(exc.code or 0)
    try:
        from monte_neo.arl_rules import sync_page
        from monte_neo.readiness import readiness
        from monte_neo.verify.sealed_holdout import SealedHoldout

        if args.sync_docs:
            for page in args.sync_docs:
                path = Path(page)
                path.write_text(sync_page(path.read_text(encoding="utf-8")), encoding="utf-8")
                console.print(f"synced {page}")
            return 0
        if not (args.certificate or args.alpha or args.live):
            raise ValueError("give at least one of --certificate, --alpha, --live")
        report = readiness(_load(args.certificate), _load(args.alpha), _load(args.live), n_trials=args.n_trials,
                           holdout=SealedHoldout(args.holdout).evidence() if args.holdout else None, rules_version=args.rules_version)
    except Exception as exc:  # input errors must not look like a level
        console.print(f"[red]readiness failed: {exc}[/]")
        return 3
    if args.format == "json":
        print(json.dumps(report, indent=2, default=str))
        return 0
    console.print(f"[bold]{report['headline']}[/]")
    console.print(report["summary"])
    for lv in report["levels"]:
        mark = "" if lv["counts"] else f" (not reached; criteria met if it were: {lv['depth_if_reached']}/4)"
        console.print(f"  ARL {lv['level']} {lv['name']}: {lv['state']}, depth {lv['depth']}/4{mark}")
    for a in report["next_actions"][:12]:
        console.print(f"  - ARL {a['level']} {a['criterion']} {a['state']}: {a['command']}")
    console.print(f"[dim]{report['authorship']}[/]")
    console.print(f"[dim]{report['disclaimer']}[/]")
    return 0


__all__ = ["main"]
