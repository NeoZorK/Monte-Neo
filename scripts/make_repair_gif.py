"""Render docs/assets/demo-repair.gif: `monte-neo repair --demo`, three honest outcomes.

The terminal lines are copied from a real `monte-neo repair --demo --out <folder>` run (long
lines are wrapped by hand to fit the window). Re-copy them when the repair output changes.

Run: uv run python scripts/make_repair_gif.py
"""

from __future__ import annotations

from pathlib import Path

from make_demo_gif import BLU, DIM, GRN, RED, YEL, Part, build, p

OUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "demo-repair.gif"
DISCLAIMER = "Not investment advice: a research example, not a call to trade or a promise of profit."


def head(name: str, verdict: str, color: tuple[int, int, int], rest: str) -> list[Part]:
    return [p(f"{name}: "), p(verdict, color, True), p(f" — {rest}")]


SCENES: list[list[list[Part]]] = [
    [[p("$ ", GRN), p("monte-neo repair --demo --out repair-demo")]],
    [
        head("leak", "REPAIRED_NO_EDGE", YEL, "Defects repaired, and no edge is left: the profit was"),
        [p("  in the defect.", DIM)],
        [p("  before: REJECT, net -49.9%")],
        [p("  correction R1 negative_shift: df['close'].shift(-1) -> df['close'].shift(1)")],
        [p("  correction R2 delay: the signal changed after it was shown: act one bar later")],
        [p("  lockbox (opened once, from 2024-01-01): "), p("REJECT", RED, True), p(", net -42.1%")],
    ],
    [
        [p("")],
        head("flicker", "REPAIRED", GRN, "Defects repaired; the lockbox, opened once, still earns after costs and is not rejected."),
        [p("  before: "), p("REJECT", RED, True), p(", net -85.4%")],
        [p("  chosen on the first part of the history: R5 [('smooth', {'span': 20})]")],
        [p("  defects on the development part: 6 -> 1; trials counted: 10")],
        [p("  lockbox (opened once, from 2017-10-01): NEEDS_MORE_EVIDENCE, net +64.6%")],
    ],
    [
        [p("")],
        head("unseeded", "NOT_REPAIRABLE", RED, "Not repairable automatically: see what is needed from"),
        [p("  you.", DIM)],
        [p("  needs you: determinism: seed every random generator: a non-deterministic")],
        [p("  signal cannot be verified")],
    ],
    [
        [p("")],
        [p("# Repairs without overfitting. Tells you when there is nothing to repair.", BLU)],
        [p(DISCLAIMER, DIM)],
    ],
]
PAUSES = {1: 2200, 2: 2200, 3: 1800}


def main() -> None:
    build(SCENES, PAUSES, OUT, "monte-neo repair", colors=96)


if __name__ == "__main__":
    main()
