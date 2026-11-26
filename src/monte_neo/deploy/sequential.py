"""Sequential forward test: decide as soon as the evidence is there, valid however often you look.

A fixed 13-week window wastes time on clear failures and cannot use evidence that arrives early. This module runs two
e-processes (test martingales built from bets, Ville's inequality makes them valid under continuous monitoring) on the
daily net returns of a forward record:

* ``edge``: H0 "the mean return is not above zero". Its e-value grows when the record shows a positive edge.
* ``shortfall``: H0 "the annual Sharpe ratio is at least ``target_sharpe``". Its e-value grows when the record falls short.

Returns are standardised by a volatility estimated from PAST days only and clipped to ``[-clip, clip]``, so each bet is
bounded and predictable. A hypothesis is rejected when its e-value reaches ``n_trials / alpha`` (Bonferroni over every
candidate under forward test, so running many strategies in parallel does not inflate false passes).

Decision, every day:
* ``FAIL_EARLY``: the shortfall e-value crossed the threshold after at least ``min_fail_days``.
* ``PASS``: the edge e-value crossed the threshold after at least ``min_pass_days``.
* ``INCONCLUSIVE``: ``max_days`` reached without either; treat as not passed.
* ``CONTINUE``: keep recording.

Standard library only. Validity is approximate where the standardisation and the clipping bend the null slightly; the
calibration test in ``tests/unit/test_sequential.py`` measures the false-pass rate on simulated null records.
"""

from __future__ import annotations

import math
from typing import Any

DEFAULTS: dict[str, float] = {"alpha": 0.05, "target_sharpe": 0.5, "clip": 4.0, "warmup": 10, "halflife": 30.0,
                              "min_fail_days": 21, "min_pass_days": 56, "max_days": 182, "periods_per_year": 365.0}


def _bet(history: list[float], cap: float) -> float:
    """aGRAPA bet size from past outcomes only: mean / second moment, clipped to [0, cap]."""
    if len(history) < 5:
        return min(0.05, cap)
    m = sum(history) / len(history)
    v = sum(x * x for x in history) / len(history)
    return max(0.0, min(cap, m / v if v > 0 else 0.0))


def standardise(returns: list[float], warmup: int = 10, halflife: float = 30.0, clip: float = 4.0) -> list[float]:
    """z_t = r_t / sigma_{t-1}, sigma from an exponentially weighted variance of earlier days only; first ``warmup`` days skipped."""
    lam = 0.5 ** (1.0 / halflife)
    out: list[float] = []
    var = None
    for i, r in enumerate(returns):
        if i >= warmup and var and var > 0:
            out.append(max(-clip, min(clip, r / math.sqrt(var))))
        if i < warmup:
            var = (var or 0.0) + r * r / warmup
        else:
            var = lam * (var or r * r) + (1 - lam) * r * r
    return out


def days_needed(sharpe: float, alpha: float = 0.05, power: float = 0.8, periods_per_year: float = 365.0) -> float | None:
    """Fixed-sample approximation of the days needed to show an annual Sharpe ratio ``sharpe`` is above zero.

    A sequential test needs somewhat more. The point it makes is plain: a Sharpe ratio of 1 needs years of daily data,
    so a forward record of weeks checks that nothing is broken; it cannot prove an edge of ordinary size.
    """
    if sharpe <= 0:
        return None
    z = {0.05: 1.645, 0.01: 2.326}.get(alpha, 1.645) + {0.8: 0.842, 0.9: 1.282, 0.5: 0.0}.get(power, 0.842)
    return (z / (sharpe / math.sqrt(periods_per_year))) ** 2


def evaluate(returns: list[float], n_trials: int = 1, **params: float) -> dict[str, Any]:
    """Run both e-processes over the daily net returns; returns the decision and the paths (for a chart)."""
    p = {**DEFAULTS, **params}
    z = standardise(list(returns), int(p["warmup"]), p["halflife"], p["clip"])
    mu1 = p["target_sharpe"] / math.sqrt(p["periods_per_year"])  # the target as a daily standardised mean
    threshold = max(1, int(n_trials)) / p["alpha"]
    cap_edge, cap_short = 0.5 / p["clip"], 0.5 / (p["clip"] + mu1)
    k_edge = k_short = 1.0
    seen_edge: list[float] = []
    seen_short: list[float] = []
    path_edge, path_short = [], []
    decision, day = "CONTINUE", None
    warm = int(p["warmup"])
    for i, x in enumerate(z):
        lam_e, lam_s = _bet(seen_edge, cap_edge), _bet(seen_short, cap_short)
        k_edge *= 1.0 + lam_e * x
        k_short *= 1.0 + lam_s * (mu1 - x)
        seen_edge.append(x)
        seen_short.append(mu1 - x)
        path_edge.append(k_edge)
        path_short.append(k_short)
        days = warm + i + 1
        if decision == "CONTINUE":
            if k_short >= threshold and days >= p["min_fail_days"]:
                decision, day = "FAIL_EARLY", days
            elif k_edge >= threshold and days >= p["min_pass_days"]:
                decision, day = "PASS", days
            elif days >= p["max_days"]:
                decision, day = "INCONCLUSIVE", days
    return {
        "schema": "sequential-forward/1", "decision": decision, "decided_on_day": day, "days": len(returns),
        "threshold": threshold, "n_trials": max(1, int(n_trials)), "e_edge": k_edge, "e_shortfall": k_short,
        "params": p, "path_edge": path_edge, "path_shortfall": path_short,
        "days_needed_for_target": days_needed(p["target_sharpe"], p["alpha"], 0.8, p["periods_per_year"]),
        "explain": {
            "CONTINUE": "not enough evidence either way yet: keep recording",
            "PASS": "the record shows a positive edge with the evidence required for all candidates under test",
            "FAIL_EARLY": f"the record falls short of a Sharpe ratio of {p['target_sharpe']} with the required evidence: stop it",
            "INCONCLUSIVE": "the maximum length was reached without a decision: treat as not passed",
        }[decision],
    }
