"""``monte-neo research``: an honest strategy search (fixed split, ledger, pre-registered batches, one sealed holdout).

Exit codes: 0 done, 3 input error or a protocol rule refused the step.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from rich.console import Console

from monte_neo.research.service import ACTIONS, run_action, run_breadth

HELP_STEPS = "init -> screen -> promote -> validate -> holdout -> certify -> report -> handoff; status shows progress and ETA; forward records a frozen rule forward; funnel, family and breadth read only"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="monte-neo research", description=f"Honest strategy search. Steps: {HELP_STEPS}.")
    p.add_argument("action", choices=(*ACTIONS, "breadth"))
    p.add_argument("step", nargs="?", help="forward: freeze, record or status")
    p.add_argument("--project", default=".monte-neo/research", help="project folder (default .monte-neo/research)")
    p.add_argument("--data", help="OHLCV table (the same file at every step)")
    p.add_argument("--discovery-end", help="init: first date of the validation part")
    p.add_argument("--validation-end", help="init: first date of the sealed holdout")
    p.add_argument("--name", default="research")
    p.add_argument("--strategy", help="screen: strategy file with signal(df, **params)")
    p.add_argument("--grid", help='screen: JSON grid, for example \'{"n": [10, 20, 40]}\'')
    p.add_argument("--params", help="screen: JSON parameters of one variant")
    p.add_argument("--top", type=int, help="preregister: promote the K best not yet promoted by discovery Sharpe")
    p.add_argument("--min-sharpe", type=float, default=0.0)
    p.add_argument("--candidates", nargs="+", help="preregister: candidate ids")
    p.add_argument("--rule", help="preregister: the rule that chose the batch (written into the record)")
    p.add_argument("--batch", type=int)
    p.add_argument("--candidate", help="freeze: candidate id")
    p.add_argument("--override", action="store_true", help="freeze: open the holdout although the validation gate is closed (recorded)")
    p.add_argument("--confirm", action="store_true", help="freeze and open_holdout cannot be undone")
    p.add_argument("--signal", help="breadth: dates x names signal table (.csv or .parquet)")
    p.add_argument("--forward-returns", help="breadth: dates x names forward return table")
    p.add_argument("--returns", help="family: a folder of return files (date, return) or one wide table (date + one column per candidate)")
    p.add_argument("--periods-per-year", type=float, default=None, help="breadth and family: observations per year (breadth default 252, family inferred from the dates)")
    p.add_argument("--grammar", help="init/screen: grammar file (SOURCE or STRATEGY, and GRID or variants()): the variants to screen")
    p.add_argument("--profile", help="init: strategy profile id (see monte-neo verify --list-profiles); the report adds its coverage block per candidate")
    p.add_argument("--policy", help='init: JSON overrides of the policy, for example \'{"fdr_q": 0.05, "min_effective_n": 60}\'')
    p.add_argument("--chunk", type=int, default=25, help="screen: variants per saved chunk (default 25)")
    p.add_argument("--max-seconds", type=float, default=None, help="screen: stop after this many seconds; run the same command again to go on")
    p.add_argument("--dry-run", action="store_true", help="init: run the whole pipeline on built-in synthetic data in --project (nothing real is found, by design)")
    p.add_argument("--certify-top", type=int, default=0, help="report: certify this many top validated candidates so that each has an ARL and depth")
    p.add_argument("--out", help="report: folder for report.json and report.html (default: the project)")
    p.add_argument("--dossier", help="handoff: write the validation dossier of the champion to this folder")
    p.add_argument("--hall", help="handoff: write the Hall of Fame entry of the champion to this folder (needs --author, --name, --category)")
    p.add_argument("--author")
    p.add_argument("--category")
    p.add_argument("--tier", default="C")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def _json(text: str | None) -> Any:
    return json.loads(text) if text else None


def main(argv: list[str] | None = None) -> int:
    """Run ``monte-neo research``; returns the exit code."""
    console = Console()
    try:
        a = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return 3 if exc.code == 2 else int(exc.code or 0)
    try:
        if a.action == "breadth":
            if not (a.signal and a.forward_returns):
                raise ValueError("breadth needs --signal and --forward-returns")
            out = run_breadth(a.signal, a.forward_returns, periods_per_year=a.periods_per_year or 252.0)
        else:
            out = run_action(a.project, a.action, data=a.data, discovery_end=a.discovery_end, validation_end=a.validation_end, name=a.name, strategy=a.strategy,
                             grid=_json(a.grid), params=_json(a.params), top=a.top, min_sharpe=a.min_sharpe, candidates=a.candidates, rule=a.rule, batch=a.batch,
                             candidate=a.candidate, override=a.override, confirm=a.confirm, returns=a.returns, periods_per_year=a.periods_per_year,
                             grammar=a.grammar, profile=a.profile, policy=_json(a.policy), chunk=a.chunk, max_seconds=a.max_seconds, dry_run=a.dry_run, certify_top=a.certify_top,
                             out=a.out, step=a.step, dossier_dir=a.dossier, hall_dir=a.hall, author=a.author, category=a.category, tier=a.tier)
    except Exception as exc:  # input errors and refused steps must not look like a result
        console.print(f"[red]research {a.action} failed: {exc}[/]")
        return 3
    if a.format == "json":
        print(json.dumps(out, indent=2, default=str))
    elif a.action in ("funnel", "status", "report") or (a.action == "init" and a.dry_run):
        print(out["text"])
    elif a.action == "breadth":
        print(out["check"]["summary"])
    elif a.action == "family":
        print("\n".join(r["summary"] for r in out["rows"]))
    else:
        print(json.dumps({k: v for k, v in out.items() if k not in ("candidates", "rows", "certificate", "checks")}, indent=2, default=str)[:4000])
    return 0


__all__ = ["main"]
