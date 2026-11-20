"""Render docs/assets/demo-readiness.gif: the Alpha Readiness Level of a certificate, then its findings in plain words.

The terminal lines are copied from a real run (v0.55.0) on a certificate of a strategy that peeks at the next close:
`monte-neo readiness --certificate cert.json` and `monte-neo repair --explain cert.json` (long lines wrapped by hand).

Run: uv run python scripts/make_readiness_gif.py
"""

from __future__ import annotations

from pathlib import Path

from make_demo_gif import BLU, DIM, GRN, RED, YEL, build, p

OUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "demo-readiness.gif"
DISCLAIMER = "Not investment advice: a research example, not a call to trade or a promise of profit."

SCENES = [
    [[p("$ ", GRN), p("monte-neo readiness --certificate cert.json")]],
    [
        [p("ARL 1, depth 1/4", YEL, True), p(" (arl-rules/1, provisional)")],
        [p("ARL 1/9 — blocked at 2: the backtest is not broken (implausible_accuracy)")],
        [p("  ARL 1 Idea on clean data: met, depth 1/4")],
        [p("  ARL 2 The backtest is not broken: "), p("failed", RED, True)],
        [p("  ARL 3 It earns after costs: "), p("failed", RED, True)],
        [p("  ARL 4 The signal predicts: not assessed", DIM)],
    ],
    [
        [p("")],
        [p("$ ", GRN), p("monte-neo repair --explain cert.json")],
        [p("F07 Not profitable after costs (net_profitability)", YEL, True)],
        [p("  -> Trade less: hold longer, add a no-trade band, or smooth the signal.")],
        [p("F11 The Sharpe ratio does not survive the number of trials (deflated_sharpe)", YEL, True)],
        [p("  -> Get more independent data, or test one pre-registered idea on unseen data.")],
        [p("F12 The return is market exposure, not alpha (alpha_after_beta)", YEL, True)],
        [p("  -> Hedge the benchmark (long-short, beta-neutral) and test the residual.")],
    ],
    [
        [p("")],
        [p("# One scale from idea to live: what is proven, what blocks the next level, what to do.", BLU)],
        [p(DISCLAIMER, DIM)],
    ],
]
PAUSES = {1: 2600, 2: 2800, 3: 2200}


def main() -> None:
    build(SCENES, PAUSES, OUT, "monte-neo readiness + repair --explain", colors=64)


if __name__ == "__main__":
    main()
