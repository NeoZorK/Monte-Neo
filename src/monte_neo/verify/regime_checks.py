"""Is the evidence from one market regime only?

Uses the regime split of :func:`monte_neo.verify.breakdown.regimes` (a bar's regime is known at its start: trailing
return sign for rising / falling, trailing volatility against its median for calm / volatile). A strategy tested only
in a bull market has shown that it can ride a bull market. The row warns when

* a regime has under 10 % of the bars (it is effectively untested), or
* the strategy loses in a regime that holds at least 20 % of the bars, or
* one regime of a pair earns over 90 % of the log profit.

Idea: regime-conditional performance reporting, as in Ang and Bekaert (2002), "International asset allocation with regime
shifts", Review of Financial Studies 15(4).
"""

from __future__ import annotations

import math
from typing import Any

from monte_neo.verify.checks import check

UNTESTED_SHARE = 0.10
LOSS_SHARE = 0.20
CONCENTRATION = 0.90
PAIRS = (("rising", "falling"), ("calm", "volatile"))


def regime_stability_row(by_regime: dict[str, Any], total_return: float) -> dict[str, Any]:
    """Warn when the profit has been shown in one regime only; see the module docstring for the rules."""
    regimes = by_regime.get("regimes") or {}
    if total_return <= 0.0:
        return check("regime_stability", "statistics", "skip", "not profitable after costs")
    if not regimes:
        return check("regime_stability", "statistics", "skip", "too few bars to split into regimes")
    problems: list[str] = []
    for a, b in PAIRS:
        if a not in regimes or b not in regimes:
            continue
        for name in (a, b):
            if regimes[name]["share"] < UNTESTED_SHARE:
                problems.append(f"only {regimes[name]['share']:.0%} of the bars are {name}: untested there")
            elif regimes[name]["share"] >= LOSS_SHARE and regimes[name]["return"] <= 0.0:
                problems.append(f"loses in {name} markets ({regimes[name]['return']:+.1%} over {regimes[name]['share']:.0%} of bars)")
        logs = {n: math.log1p(max(regimes[n]["return"], -0.999999)) for n in (a, b)}
        total = logs[a] + logs[b]
        if total > 0:
            top = max((a, b), key=lambda n: logs[n])
            if logs[top] / total > CONCENTRATION and min(regimes[a]["share"], regimes[b]["share"]) >= UNTESTED_SHARE:
                problems.append(f"{logs[top] / total:.0%} of the profit comes from {top} markets")
    details = {n: {k: v[k] for k in ("bars", "share", "return", "sharpe_annualized")} for n, v in regimes.items()}
    if problems:
        return check("regime_stability", "statistics", "warn", "the evidence rests on one regime: " + "; ".join(problems), details)
    return check("regime_stability", "statistics", "pass", "the strategy has been tested in rising, falling, calm and volatile markets without loss or concentration", details)


__all__ = ["CONCENTRATION", "LOSS_SHARE", "PAIRS", "UNTESTED_SHARE", "regime_stability_row"]
