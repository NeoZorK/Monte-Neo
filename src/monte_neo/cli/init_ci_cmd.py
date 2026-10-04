"""``monte-neo init-ci``: write a GitHub Actions workflow that verifies a strategy on every pull request."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from rich.console import Console

CHECKOUT = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4"
DEFAULT_OUT = ".github/workflows/monte-neo.yml"
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "tests", "test", "__pycache__", "build", "dist", ".tox"}
DATA_SUFFIXES = (".csv", ".parquet")
FAIL_ON = ("REJECT", "NEEDS_MORE_EVIDENCE", "PASS_WITH_WARNINGS")
_SIGNAL = re.compile(r"^def\s+signal\s*\(", re.MULTILINE)


def build_parser() -> argparse.ArgumentParser:
    """Argument parser of ``monte-neo init-ci``."""
    p = argparse.ArgumentParser(
        prog="monte-neo init-ci",
        description="Write a GitHub Actions workflow that verifies your strategy on every pull request.",
    )
    p.add_argument("--strategy", help="Strategy file 'path.py[:func]' (default: found in this directory)")
    p.add_argument("--ohlcv", help="OHLCV table (.csv / .parquet) (default: found in this directory)")
    p.add_argument("--n-trials", type=int, help="How many variants were tried before this one (leave out if unknown)")
    p.add_argument("--fail-on", choices=FAIL_ON, default="REJECT", help="Lowest verdict that fails the job (default REJECT)")
    p.add_argument("--isolate", action="store_true", help="Run the strategy without network, subprocesses or file writes")
    p.add_argument("--sign", action="store_true", help="Sign the certificate with the MONTE_NEO_SIGNING_KEY repository secret")
    p.add_argument("--out", default=DEFAULT_OUT, help=f"Where to write the workflow (default {DEFAULT_OUT})")
    p.add_argument("--force", action="store_true", help="Overwrite an existing file")
    p.add_argument("--print", dest="print_only", action="store_true", help="Print the workflow instead of writing it")
    return p


def _files(root: Path, suffixes: tuple[str, ...], depth: int = 2) -> list[Path]:
    """Files under ``root`` with these suffixes, at most ``depth`` folders deep, without tool and test folders."""
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if len(rel.parts) > depth + 1 or any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts[:-1]):
            continue
        if path.is_file() and path.suffix.lower() in suffixes:
            found.append(rel)
    return found


def find_strategy(root: Path) -> tuple[str | None, list[str]]:
    """The strategy file of a project: the only Python file that defines ``signal(``, or ``strategy.py``."""
    candidates = []
    for rel in _files(root, (".py",)):
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _SIGNAL.search(text):
            candidates.append(rel.as_posix())
    if len(candidates) == 1:
        return candidates[0], candidates
    if "strategy.py" in candidates:
        return "strategy.py", candidates
    return None, candidates


def find_ohlcv(root: Path) -> tuple[str | None, list[str]]:
    """The price table of a project: the only .csv / .parquet file (preferring a ``data`` folder)."""
    tables = [rel.as_posix() for rel in _files(root, DATA_SUFFIXES)]
    in_data = [t for t in tables if t.split("/")[0] == "data"]
    for group in (in_data, tables):
        if len(group) == 1:
            return group[0], tables
    return None, tables


def render_workflow(
    *, ohlcv: str, strategy: str, version: str, n_trials: int | None = None, fail_on: str = "REJECT",
    isolate: bool = False, sign: bool = False,
) -> str:
    """The workflow text. ``version`` is the release the action is pinned to (for example ``v0.51.0``)."""
    lines = [
        "name: Monte-Neo verify",
        "",
        "on:",
        "  pull_request:",
        "  push:",
        "    branches: [main]",
        "  workflow_dispatch:",
        "",
        "permissions:",
        "  contents: read",
        "  pull-requests: write  # only for the verdict comment on pull requests",
        "",
        "jobs:",
        "  verify:",
        "    runs-on: ubuntu-latest",
        "    timeout-minutes: 20",
        "    steps:",
        f"      - uses: {CHECKOUT}",
        "      # Pin to a commit SHA instead of the tag if your policy asks for it.",
        f"      - uses: NeoZorK/Monte-Neo@{version}",
        "        with:",
        f"          ohlcv: {ohlcv}",
        f"          strategy: {strategy}",
    ]
    if n_trials is not None:
        lines.append(f'          n-trials: "{n_trials}"')
    else:
        lines.append('          # n-trials: "12"  # how many variants you tried before this one')
    lines += [f"          fail-on: {fail_on}", '          comment: "true"', '          upload-certificate: "true"']
    if isolate:
        lines.append('          isolate: "true"')
    if sign:
        lines.append("          signing-key: ${{ secrets.MONTE_NEO_SIGNING_KEY }}")
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace, console: Console | None = None, root: Path | None = None) -> int:
    """Write (or print) the workflow. Returns 0, or 3 on a usage problem."""
    from monte_neo._version import __version__

    console = console or Console(highlight=False)
    root = root or Path.cwd()
    strategy, strategies = (args.strategy, []) if args.strategy else find_strategy(root)
    ohlcv, tables = (args.ohlcv, []) if args.ohlcv else find_ohlcv(root)
    notes: list[str] = []
    if strategy is None:
        notes.append(
            "no strategy file found" if not strategies else f"several files define signal(): {', '.join(strategies)}"
        )
        strategy = "strategy.py"
    if ohlcv is None:
        notes.append("no single price table found" if not tables else f"several price tables: {', '.join(tables)}")
        ohlcv = "data/prices.csv"
    text = render_workflow(
        ohlcv=ohlcv, strategy=strategy, version=__version__ if __version__.startswith("v") else f"v{__version__}",
        n_trials=args.n_trials, fail_on=args.fail_on, isolate=args.isolate, sign=args.sign,
    )
    if args.print_only:
        sys.stdout.write(text)
        return 0
    target = Path(args.out)
    target = target if target.is_absolute() else root / target
    if target.exists() and not args.force:
        console.print(f"[red]{target} already exists: pass --force to overwrite, or --print to see the workflow[/]")
        return 3
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    console.print(f"wrote {target}")
    console.print(f"  strategy: {strategy}\n  prices:   {ohlcv}")
    for note in notes:
        console.print(f"[yellow]  note: {note}; the file uses a placeholder, edit it[/]")
    console.print("Next: commit the file and open a pull request; the job fails when the verdict is " + args.fail_on + " or worse.")
    if args.sign:
        console.print("  Signing: monte-neo verify --keygen ci, then store ci.key as the repository secret MONTE_NEO_SIGNING_KEY.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``monte-neo init-ci``."""
    try:
        args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return 3 if exc.code == 2 else int(exc.code or 0)
    return run(args)


__all__ = ["build_parser", "find_ohlcv", "find_strategy", "main", "render_workflow", "run"]
