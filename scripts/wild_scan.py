"""Scan strategy files you cloned and report only aggregates (no file names, no repository names, no code).

python scripts/wild_scan.py --out wild-report.md ~/wild/repo-a ~/wild/repo-b

For each ``.py`` file that looks like a trading strategy it records the framework (from the imports), runs the static
look-ahead lint of the verifier on the source, and, for files with ``def signal(df)``, nothing else: dynamic checks need
data and a safe place to run foreign code, so they are not done here. The report says how many files, which frameworks,
what share has at least one failing / warning finding, and how often each rule fires. Do not publish names, links or code
of the projects: the point is the rate, not the blame.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path

from monte_neo.verify.lint import lint_source

FRAMEWORKS = {
    "freqtrade": ("freqtrade",),
    "backtrader": ("backtrader",),
    "backtesting.py": ("backtesting",),
    "vectorbt": ("vectorbt",),
    "zipline": ("zipline",),
    "lean": ("AlgorithmImports", "QuantConnect"),
    "nautilus": ("nautilus_trader",),
    "bt": ("bt",),
    "pandas-ta/ta-lib": ("pandas_ta", "talib", "ta"),
}
HINTS = ("populate_indicators", "populate_entry_trend", "populate_buy_trend", "def next(", "def on_data", "def init(", "def signal(", "def generate", "strategy", "Strategy", "backtest", "signals")
MAX_BYTES = 400_000


def framework_of(tree: ast.AST) -> str:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    for fw, keys in FRAMEWORKS.items():
        if names & set(keys):
            return fw
    return "plain pandas/numpy" if names & {"pandas", "numpy"} else "other"


def scan(roots: list[Path]) -> dict:
    files = 0
    by_fw: Counter[str] = Counter()
    fail_fw: Counter[str] = Counter()
    warn_fw: Counter[str] = Counter()
    rules: Counter[str] = Counter()
    skipped = 0
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if any(part in {".git", "node_modules", "site-packages", "venv", ".venv", "tests", "test"} for part in path.parts):
                continue
            try:
                if path.stat().st_size > MAX_BYTES:
                    skipped += 1
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(text)
            except (OSError, SyntaxError, ValueError):
                skipped += 1
                continue
            if not any(h in text for h in HINTS):
                continue
            fw = framework_of(tree)
            result = lint_source(text)
            files += 1
            by_fw[fw] += 1
            if result["status"] == "fail":
                fail_fw[fw] += 1
            elif result["status"] == "warn":
                warn_fw[fw] += 1
            for rule in {f["rule"] for f in result["findings"]}:
                rules[rule] += 1
    return {"files": files, "skipped": skipped, "frameworks": dict(by_fw), "fail": dict(fail_fw), "warn": dict(warn_fw), "rules": dict(rules.most_common())}


def render(r: dict) -> str:
    n = max(r["files"], 1)
    lines = [
        "# Wild scan (aggregates only)", "",
        f"Files that look like strategies: {r['files']} (skipped: {r['skipped']} unreadable, unparsable or over {MAX_BYTES // 1000} KB).",
        f"At least one failing finding: {sum(r['fail'].values())} ({sum(r['fail'].values()) / n:.1%}); only warnings: {sum(r['warn'].values())} ({sum(r['warn'].values()) / n:.1%}).",
        "", "| Framework | Files | Failing | Warnings only |", "|---|---|---|---|",
    ]
    for fw, c in sorted(r["frameworks"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {fw} | {c} | {r['fail'].get(fw, 0)} ({r['fail'].get(fw, 0) / c:.0%}) | {r['warn'].get(fw, 0)} ({r['warn'].get(fw, 0) / c:.0%}) |")
    lines += ["", "## Rules (files where the rule fires)", "", "| Rule | Files |", "|---|---|"]
    lines += [f"| `{k}` | {v} |" for k, v in r["rules"].items()]
    lines += ["", "Static lint only: a finding is a place to look, not a proven leak, and a clean file can still leak.", ""]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("roots", nargs="+", help="directories with cloned repositories")
    p.add_argument("--out", default="wild-report.md")
    p.add_argument("--json", help="also write the counts as JSON")
    a = p.parse_args()
    roots = [Path(x).expanduser() for x in a.roots]
    missing = [str(r) for r in roots if not r.is_dir()]
    if missing:
        print(f"not a directory: {', '.join(missing)}", file=sys.stderr)
        return 3
    result = scan(roots)
    Path(a.out).write_text(render(result), encoding="utf-8")
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
