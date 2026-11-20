"""Why a search did not pass, in groups of causes, and what to do next that adds *information*.

The next actions never ask for another variant: more variants on the same data spend the same sample again and raise the cost of the
search. They ask for data the search has not seen (a later period, another market, the forward record), for measured instead of assumed
costs, for the right benchmark, or for a fix of a defect. The groups are read from the validation statistics of the family and from the
certificate rows of the candidates that were certified.
"""

from __future__ import annotations

from statistics import NormalDist
from typing import Any

_N = NormalDist()
ORDER = ("implementation", "multiple_testing", "few_observations", "costs", "beta_not_alpha", "one_regime", "capacity", "survivorship")
TITLES = {
    "implementation": "The backtest itself may be wrong",
    "multiple_testing": "The search explains the result",
    "few_observations": "Too few independent observations",
    "costs": "Costs eat the edge",
    "beta_not_alpha": "Market exposure instead of alpha",
    "one_regime": "One regime carries the result",
    "capacity": "Too large for the market it trades",
    "survivorship": "The universe may be survivors",
}
ACTIONS = {
    "implementation": ["Fix what the failed look-ahead or data checks name first: a result with look-ahead is not evidence, whatever else it shows."],
    "multiple_testing": [
        "Do not add variants: they spend the same sample and raise the price of the search. Collect data the search has not seen: a later period, another market, or the forward record of the frozen rule (`research forward`).",
        "If a second batch is unavoidable, validate it on a new window, not on the one already read.",
    ],
    "few_observations": ["Wait for or add independent data: the years needed for the observed Sharpe to stand out at this number of tries are given in the evidence."],
    "costs": ["Replace assumed costs with measured ones (recorded quotes or real fills) and verify the frozen rule again; do not re-tune the rule to the costs."],
    "beta_not_alpha": ["Judge it against the benchmark of its profile and add an independent market as new data; a return that follows the market is not shown to be skill."],
    "one_regime": ["Extend the history to include another regime (a bear market, a range) or record forward through one; the result is not shown outside the regime that made it."],
    "capacity": ["State the capital you plan to run and test on instruments with more traded value; recorded quotes show what the fills would really cost."],
    "survivorship": ["Add the price history of delisted or dropped instruments, or define the universe by a rule known on each date."],
}
BAD = ("fail", "warn")


def years_needed(sharpe_annual: float, n_trials: int, *, alpha: float = 0.05, power: float = 0.80) -> float | None:
    """Years of data for an annual Sharpe to be detected at ``n_trials`` tries (``None`` if the Sharpe is not positive)."""
    if sharpe_annual <= 0:
        return None
    z = _N.inv_cdf(1.0 - alpha / max(1, n_trials)) + _N.inv_cdf(power)
    return (z / sharpe_annual) ** 2


def _status(checks: dict[str, dict[str, Any]], *ids: str) -> list[str]:
    return [f"{i}: {checks[i]['status']}" for i in ids if i in checks and checks[i]["status"] in BAD]


def diagnose(facts: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Groups of causes with evidence and next actions.

    ``facts``: ``n_trials``, ``spa_passes``, ``years`` (validation length), ``best_sharpe_annual``, ``min_detectable_sharpe_annual``, ``n_eff``,
    ``any_beats_null``, ``any_significant``. ``candidates``: dicts with optional ``checks`` (``{id: row}`` of the candidate's certificate).
    """
    groups: dict[str, list[str]] = {g: [] for g in ORDER}
    n = int(facts.get("n_trials", 1))
    if not facts.get("spa_passes", False):
        groups["multiple_testing"].append("the family SPA does not reject: luck cannot be excluded as the source of the best result")
    if not facts.get("any_significant", False):
        groups["multiple_testing"].append("no candidate is significant after the Romano-Wolf stepdown")
    if not facts.get("any_beats_null", False):
        groups["multiple_testing"].append("no Sharpe is above what luck alone delivers for this many tries")
    best, mde = float(facts.get("best_sharpe_annual", 0.0)), float(facts.get("min_detectable_sharpe_annual", 0.0))
    if mde and best < mde:
        yrs = years_needed(best, n)
        groups["few_observations"].append(f"the best Sharpe {best:.2f} is below the {mde:.2f} this search can detect on {facts.get('years', 0):.1f} years"
                                          + (f"; about {yrs:.0f} years would be needed at {n} tries" if yrs else ""))
    for c in candidates:
        ck = c.get("checks") or {}
        cid = c.get("id", "?")
        for g, ids in (("implementation", ("lookahead_truncation", "lookahead_perturbation", "implausible_accuracy", "data_independence", "data_integrity")),
                       ("few_observations", ("sample_size", "min_backtest_length")),
                       ("costs", ("net_profitability", "cost_sensitivity", "cost_realism", "market_impact")),
                       ("beta_not_alpha", ("alpha_after_beta", "residual_alpha", "benchmark_comparison", "factor_exposure")),
                       ("one_regime", ("regime_stability", "period_consistency", "rolling_stability", "holdout_consistency")),
                       ("capacity", ("capacity", "participation_limit", "market_impact")),
                       ("survivorship", ("survivorship",))):
            hit = _status(ck, *ids)
            if g == "implementation":
                hit = [h for h in hit if h.endswith(": fail")]  # a warning is not a defect
            groups[g] += [f"{cid}: {h}" for h in hit]
    out = []
    for g in ORDER:
        ev = list(dict.fromkeys(groups[g]))
        if ev:
            sev = "high" if g in ("implementation", "multiple_testing") else "medium"
            out.append({"id": g, "title": TITLES[g], "severity": sev, "evidence": ev[:8], "next_actions": ACTIONS[g]})
    nxt = list(dict.fromkeys(a for g in out for a in g["next_actions"]))
    return {"groups": out, "next_actions": nxt, "passed": not out}


__all__ = ["ACTIONS", "ORDER", "TITLES", "diagnose", "years_needed"]
