"""Render docs/assets/demo-phantom.gif: `monte-neo verify --demo-phantom`, profit from accounting on pure noise.

The terminal lines are copied from a real `monte-neo verify --demo-phantom` run (v0.55.0; long lines wrapped by hand).
Re-copy them when the output changes.

Run: uv run python scripts/make_phantom_gif.py
"""

from __future__ import annotations

from pathlib import Path

from make_demo_gif import BLU, DIM, GRN, RED, YEL, build, p

OUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "demo-phantom.gif"
DISCLAIMER = "Not investment advice: a research example, not a call to trade or a promise of profit."

SCENES = [
    [[p("$ ", GRN), p("monte-neo verify --demo-phantom")]],
    [
        [p("Demo: a z-score pairs rule on two independent random walks (no relationship,")],
        [p("no edge possible).")],
    ],
    [
        [p("")],
        [p("spread-change accounting (wrong)", YEL, True)],
        [p("  --null-test "), p("REJECT", RED, True), p("  profitable on pure noise, on 40 independent")],
        [p("  random-walk sets: median Sharpe +9.13, 100% positive, median t +4.36.")],
    ],
    [
        [p("leg accounting (tradable)", GRN, True)],
        [p("  --null-test "), p("PASS", GRN, True), p("  no edge on noise: median Sharpe +0.27, 57% positive.")],
    ],
    [
        [p("")],
        [p("The fix is one line: book pnl = position.shift(1) * (d_y - beta.shift(1) * d_x),", BLU)],
        [p("not position * diff(spread).", BLU)],
        [p(DISCLAIMER, DIM)],
    ],
]
PAUSES = {2: 2400, 3: 2000, 4: 2600}


def main() -> None:
    build(SCENES, PAUSES, OUT, "monte-neo verify --demo-phantom", colors=64)


if __name__ == "__main__":
    main()
