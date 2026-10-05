"""A small mutation check of the verifier's core: change one thing, run the tests, see whether they notice.

For each target file the script lists mutation sites (a comparison flipped, an operator swapped, a constant moved by one,
``and`` turned into ``or``, a ``not`` dropped), samples ``--sample`` of them with a fixed seed, writes each mutant to a
temporary copy of the package and runs the target's tests against it. A mutant the tests fail on is *killed*.
Usage: python scripts/mutation_check.py --sample 30 [--out docs/development/mutation-report.md]
"""

from __future__ import annotations

import argparse
import ast
import copy
import os
import random
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "monte_neo"
TARGETS = {
    "verify/lookahead.py": ["tests/unit/test_verify_probes.py", "tests/unit/test_verify_stateful.py", "tests/traps/test_trap_suite.py"],
    "verify/repaint.py": ["tests/zoo/test_zoo_repaint.py"],
    "verify/stats.py": ["tests/unit/test_verify_stats_ingest.py", "tests/zoo/test_zoo_statistics.py"],
    "verify/quality.py": ["tests/unit/test_verify_quality.py", "tests/zoo/test_zoo_data.py"],
    "verify/ledger.py": ["tests/unit/test_verify_ledger.py"],
    "verify/history.py": ["tests/unit/test_stage10_tools.py"],
}
SWAPS = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt}
ARITH = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}


def sites(tree: ast.AST) -> list[tuple[str, int]]:
    out = []
    for i, node in enumerate(ast.walk(tree)):
        if isinstance(node, ast.Compare) and type(node.ops[0]) in SWAPS:
            out.append(("compare", i))
        elif isinstance(node, ast.BinOp) and type(node.op) in ARITH:
            out.append(("arith", i))
        elif isinstance(node, ast.BoolOp):
            out.append(("boolop", i))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            out.append(("not", i))
        elif isinstance(node, ast.Constant) and isinstance(node.value, int | float) and not isinstance(node.value, bool) and node.value not in (0, 1):
            out.append(("constant", i))
    return out


def mutate(source: str, kind: str, index: int) -> str:
    tree = ast.parse(source)
    for i, node in enumerate(ast.walk(tree)):
        if i != index:
            continue
        if kind == "compare":
            node.ops[0] = SWAPS[type(node.ops[0])]()
        elif kind == "arith":
            node.op = ARITH[type(node.op)]()
        elif kind == "boolop":
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        elif kind == "not":
            return ast.unparse(ast.fix_missing_locations(_Replace(node).visit(copy.deepcopy(tree))))
        else:
            node.value = node.value + (1 if isinstance(node.value, int) else 0.5 * (abs(node.value) or 1.0))
    return ast.unparse(tree)


class _Replace(ast.NodeTransformer):
    def __init__(self, target: ast.AST) -> None:
        self.target = target

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:  # noqa: N802
        if (node.lineno, node.col_offset) == (self.target.lineno, self.target.col_offset) and isinstance(node.op, ast.Not):
            return self.generic_visit(node.operand)
        return self.generic_visit(node)


def run_mutant(target: str, tests: list[str], kind: str, index: int, source: str, timeout: int) -> bool:
    """True when the tests fail (the mutant is killed)."""
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(PKG, Path(tmp) / "monte_neo", ignore=shutil.ignore_patterns("__pycache__", "*.nbc", "*.nbi"))
        (Path(tmp) / "monte_neo" / target).write_text(mutate(source, kind, index), encoding="utf-8")
        env = {**os.environ, "PYTHONPATH": tmp, "ZOO_LEVEL": "lite"}
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-x", "-q", "-W", "ignore", "-p", "no:cacheprovider", *tests],
                cwd=ROOT, env=env, capture_output=True, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            return True  # a mutant that hangs the tests is noticed
        return proc.returncode != 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sample", type=int, default=30)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--jobs", type=int, default=3)
    p.add_argument("--timeout", type=int, default=240)
    p.add_argument("--only", help="comma separated targets (default all)")
    p.add_argument("--out", default=str(ROOT / "docs" / "development" / "mutation-report.md"))
    a = p.parse_args()
    rows, survivors = [], []
    for target, tests in TARGETS.items():
        if a.only and target not in a.only.split(","):
            continue
        source = (PKG / target).read_text(encoding="utf-8")
        found = sites(ast.parse(source))
        picked = random.Random(a.seed).sample(found, min(a.sample, len(found)))
        with ThreadPoolExecutor(a.jobs) as pool:
            killed = list(pool.map(lambda s: run_mutant(target, tests, s[0], s[1], source, a.timeout), picked))
        rows.append((target, len(found), len(picked), sum(killed)))
        survivors += [(target, s[0], s[1]) for s, k in zip(picked, killed, strict=True) if not k]
        print(f"{target}: {sum(killed)}/{len(picked)} killed", flush=True)
    lines = [
        "# Мутационная проверка ядра (внутренний документ)", "",
        "Генерируется `scripts/mutation_check.py`: в файл вносится одно изменение (сравнение, оператор, константа, `and`/`or`, `not`), "
        "запускаются тесты файла; мутант «убит», если тесты упали. Выборка фиксирована (`--seed`).", "",
        "| Файл | Мест для мутаций | В выборке | Убито | Доля |", "|---|---|---|---|---|",
    ]
    lines += [f"| `{t}` | {n} | {m} | {k} | {k / max(m, 1):.0%} |" for t, n, m, k in rows]
    total_m, total_k = sum(r[2] for r in rows), sum(r[3] for r in rows)
    lines += ["", f"Итого убито {total_k} из {total_m} ({total_k / max(total_m, 1):.0%}). Цель плана: не менее 80 %.", ""]
    if survivors:
        lines += ["## Выжившие мутанты (разобрать: тест, эквивалентный мутант или пробел)", ""] + [f"- `{t}`: {kind} #{i}" for t, kind, i in survivors]
    Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
