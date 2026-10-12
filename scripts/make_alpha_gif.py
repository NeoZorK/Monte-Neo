"""Render docs/assets/demo-alpha.gif: `monte-neo alpha --demo --aum 2e5`, a planted edge.

The terminal lines are copied from a real `monte-neo alpha --demo --aum 2e5` run (the check
table is cut to the rows that tell the story). Re-copy them when the alpha output changes.

Run: uv run python scripts/make_alpha_gif.py
"""

from __future__ import annotations

from pathlib import Path

from make_demo_gif import BLU, DIM, GRN, RED, YEL, Part, build, p

OUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "demo-alpha.gif"
DISCLAIMER = "Not investment advice: a research example, not a call to trade or a promise of profit."
COLORS = {"pass": GRN, "fail": RED, "warn": YEL, "info": DIM}


def row(name: str, status: str, summary: str) -> list[Part]:
    return [p(f"  {name:<23}"), p(f"{status:<5}", COLORS[status], status != "info"), p(summary)]


SCENES: list[list[list[Part]]] = [
    [[p("$ ", GRN), p("monte-neo alpha --demo --aum 2e5")]],
    [
        [p("signal with a planted edge  "), p("PASS_WITH_WARNINGS", YEL, True)],
        row("ic", "info", "mean rank IC 0.0565 (t=9.5, ICIR 0.35)"),
        row("signal_placebo", "pass", "beats permuted-score placebos (p=0.005)"),
        row("market_impact", "pass", "at AUM 2e+05: net 39.26% per year"),
        row("rebalance_timing_luck", "warn", "annual net return by rebalance day:"),
        [p("      min -20.68%, median -1.51%, max 17.93% (k=21)", DIM)],
        row("residual_alpha", "pass", "residual alpha t 7.1 clears the 3.0 hurdle"),
        [p("  ARL 6/9 — blocked at 7: tradable and robust (rebalance_timing_luck)", YEL, True)],
    ],
    [
        [p("")],
        [p("pure noise score  "), p("REJECT", RED, True)],
        row("ic", "warn", "mean rank IC -0.0079 (t=-1.4): no evidence"),
        row("signal_placebo", "fail", "not above permuted-score placebos (p=0.776)"),
        row("market_impact", "fail", "net -49.30% per year at AUM 2e+05"),
        [p("  ARL 2/9 — blocked at 3: it earns after costs (market_impact)", RED, True)],
    ],
    [
        [p("")],
        [p("# A significant IC is not yet a tradable alpha.", BLU)],
        [p(DISCLAIMER, DIM)],
    ],
]
PAUSES = {1: 2600, 2: 2000}


def main() -> None:
    build(SCENES, PAUSES, OUT, "monte-neo alpha", colors=96)


if __name__ == "__main__":
    main()
