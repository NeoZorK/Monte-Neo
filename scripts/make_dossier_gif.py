"""Render docs/assets/demo-dossier.gif: a certificate turned into an SR 11-7 validation dossier.

The terminal lines are copied from real runs of `monte-neo verify ... --out cert.json` (the
momentum trap strategy on the planted-momentum hourly data, 1 bps commission and 1 bps slippage)
and `monte-neo dossier --certificate cert.json --framework sr11-7`. Re-copy them when the
output changes; the certificate id changes with every release.

Run: uv run python scripts/make_dossier_gif.py
"""

from __future__ import annotations

from pathlib import Path

from make_demo_gif import BLU, DIM, GRN, YEL, Part, build, p

OUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "demo-dossier.gif"
DISCLAIMER = "Not investment advice: a research example, not a call to trade or a promise of profit."


def check(name: str, status: str, summary: str) -> list[Part]:
    return [p(f"  {name:<24}"), p(f"{status:<5}", YEL if status == "warn" else GRN, True), p(summary)]


SCENES: list[list[list[Part]]] = [
    [[p("$ ", GRN), p("monte-neo verify --ohlcv prices.csv --strategy strat.py --out cert.json")]],
    [
        [p("PASS_WITH_WARNINGS", YEL, True), p("  certificate 8d7521a35bf7eb61", DIM)],
        check("lookahead_truncation", "pass", "truncation probe: no leak detected"),
        check("net_profitability", "pass", "net total return +175.07% after costs"),
        check("delay_sensitivity", "warn", "profit vanishes with 1 bar delay"),
        check("timing_significance", "pass", "beats 100% of 200 shifted copies (p 0.005)"),
    ],
    [
        [p("")],
        [p("$ ", GRN), p("monte-neo dossier --certificate cert.json --framework sr11-7")],
        [p("wrote dossier/dossier.html (+ dossier.json, certificate.json, environment.json,")],
        [p("  REPRODUCE.md, limitations.md)")],
        [p("verdict PASS_WITH_WARNINGS · Federal Reserve SR 11-7 / OCC 2011-12:")],
        [p("  5 of 9 clauses covered by evidence", YEL, True)],
    ],
    [
        [p("")],
        [p("$ ", GRN), p("ls dossier")],
        [p("REPRODUCE.md  certificate.json  dossier.html  dossier.json")],
        [p("environment.json  limitations.md")],
        [p("")],
        [p("# Evidence for a validation, not a statement of compliance.", BLU)],
        [p(DISCLAIMER, DIM)],
    ],
]
PAUSES = {1: 2200, 2: 2400}


def main() -> None:
    build(SCENES, PAUSES, OUT, "monte-neo dossier", colors=96)


if __name__ == "__main__":
    main()
