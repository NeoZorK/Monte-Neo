"""Build the honesty scorecard: how often the verifier catches leaks and spares honest strategies.

Runs the hypothesis zoo (``--level lite`` direct forms, ``full`` all six disguises) and writes a markdown page with
Wilson 95 % intervals per class and the list of known gaps. Usage: python scripts/zoo_scorecard.py [--level full] [--out PATH]
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "zoo"))

from zoo_run import cases, known_gaps, outcome_ok, run_case  # noqa: E402


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - r) / d), min(1.0, (c + r) / d)


CLASSES = {
    "test_zoo_repaint": "A14 repainting (history and forming bar)", "test_zoo_data": "A4 data defects (21 x 3 frequencies)",
    "test_zoo_economics": "A5 execution and economics", "test_zoo_statistics": "A6 statistics and method",
    "test_zoo_claims": "A7 claims", "test_zoo_metamorphic": "A9 metamorphic relations", "test_zoo_universe": "A10 universes",
    "test_zoo_ml": "A11 machine learning", "test_zoo_quotes": "A12 quotes", "test_zoo_fuzz": "A13 engine fuzzing",
    "test_zoo_fixes": "suggest_fix", "test_zoo_labels": "labels checked by the independent oracle",
}


def other_classes() -> list[str]:
    """Pass counts of the other zoo files, from one pytest run (a failure here fails CI; the table is evidence, not a score)."""
    import subprocess
    import tempfile
    import xml.etree.ElementTree as ET

    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "zoo.xml"
        subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-W", "ignore", "-p", "no:cacheprovider", "-n", "4", "--junitxml", str(xml),
             *(str(ROOT / "tests" / "zoo" / f"{name}.py") for name in CLASSES)],
            check=False, capture_output=True, cwd=ROOT,
        )
        counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for case in ET.parse(xml).getroot().iter("testcase"):
            name = case.get("classname", "").split(".")[-1]
            if name in CLASSES and case.find("skipped") is None:
                counts[name][1] += 1
                counts[name][0] += case.find("failure") is None and case.find("error") is None
    out = ["", "## The other classes", "", "| Class | Passing | Cases |", "|---|---|---|"]
    out += [f"| {CLASSES[n]} | {k} | {m} |" for n, (k, m) in sorted(counts.items(), key=lambda kv: CLASSES[kv[0]])]
    return out


def build(level: str) -> str:
    rows: dict[str, list[bool]] = defaultdict(list)
    for _case_id, _mech, _form, leaks, row in cases(level):
        label = f"{'Leak' if leaks else 'Honest'}: {row[1]}"
        rows[label].append(outcome_ok(leaks, run_case(row, _form)))
    out = [
        "# Honesty scorecard", "",
        f"Generated from the hypothesis zoo (level `{level}`). A *leak* counts as caught when the truncation or perturbation probe fails it;",
        "an *honest* strategy counts as correct when no accusing check fails it. Intervals are Wilson 95 %.", "",
        "| Class | Correct | Cases | Rate | 95 % interval |", "|---|---|---|---|---|",
    ]
    for label, res in sorted(rows.items()):
        k, n = sum(res), len(res)
        lo, hi = wilson(k, n)
        out.append(f"| {label} | {k} | {n} | {k / n:.1%} | {lo:.1%} – {hi:.1%} |")
    out += other_classes()
    gaps = known_gaps()
    out += ["", "## Known gaps", "", "Cases the verifier gets wrong today. They are tracked in `tests/zoo/known_gaps.json`; a new miss fails CI.", ""]
    out += [f"- `{k}`: {v}" for k, v in sorted(gaps.items())] or ["- none"]
    return "\n".join(out) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--level", choices=["lite", "full"], default="lite")
    p.add_argument("--out", default=str(ROOT / "docs" / "guides" / "honesty-scorecard.md"))
    a = p.parse_args()
    Path(a.out).write_text(build(a.level), encoding="utf-8")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
