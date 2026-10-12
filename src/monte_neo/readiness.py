"""Alpha Readiness Level (ARL 1-9): one line a research committee can read, from idea to capital.

Like a technology readiness level, each level asks for evidence that the level below cannot give. The level is the
highest one whose requirements, and those of every level below it, are met. A level whose evidence was not produced is
**not assessed**, never passed: the report then names the run that would assess it (for example ``--aum`` or ``--book``).

Evidence comes from a ``strategy-verdict/1`` certificate, an ``alpha-report/1`` and a ``live-monitor/1`` report, as
check rows. A requirement is a list of alternatives; one alternative is met when all of its checks are present (not
skipped) with an allowed status. Level 2 also fails on any failed look-ahead check, whichever produced it.

The ARL rates the **evidence**, not the investment: an ARL of 7 is not a recommendation to trade.
"""

from __future__ import annotations

from typing import Any

from monte_neo import disclaimer

READINESS_SCHEMA_ID = "alpha-readiness/1"
OK = ("pass", "info")
SOFT = ("pass", "info", "warn")

# level: (name, requirements, how to produce the evidence); requirement = alternatives; alternative = ((id, statuses), ...)
LEVELS: dict[int, tuple[str, list[list[tuple[tuple[str, tuple[str, ...]], ...]]], str]] = {
    1: ("Idea on clean data", [[(("data_integrity", SOFT),), (("ic", OK + ("warn",)),)]], "monte-neo verify or monte-neo alpha"),
    2: ("The backtest is not broken", [[(("lookahead_truncation", OK),), (("universe_lookahead", SOFT),)]],
        "monte-neo verify --strategy (probes need code), or alpha with --membership"),
    3: ("It earns after costs", [[(("net_profitability", OK),), (("market_impact", SOFT),)]],
        "monte-neo verify, or monte-neo alpha --aum"),
    4: ("The signal predicts", [[(("ic", OK), ("signal_placebo", OK)), (("timing_significance", OK),)]],
        "monte-neo alpha (scores), or verify (timing test)"),
    5: ("It is new alpha", [[(("residual_alpha", OK), ("hidden_short_volatility", OK))]], "monte-neo alpha (attribution)"),
    6: ("It survives the search", [[(("deflated_sharpe", OK),), (("hlz_hurdle", OK), ("min_backtest_length", SOFT))]],
        "verify with --n-trials / --ledger, or alpha with --n-trials"),
    7: ("Tradable and robust", [
        [(("market_impact", SOFT),), (("capacity", SOFT),)],
        [(("synthetic_market_null", OK), ("universe_subsampling", SOFT), ("start_date_sensitivity", OK)),
         (("period_consistency", OK), ("delay_sensitivity", OK))],
        [(("rebalance_timing_luck", OK),), (("cost_margin", OK),)],
    ], "alpha with --aum (robustness runs by default), or verify with volume data"),
    8: ("It adds to your book", [[(("marginal_sharpe", OK),)]], "monte-neo alpha --book book.csv"),
    9: ("Confirmed live", [[(("live_vs_backtest", OK), ("alpha_death_monitor", OK))]], "monte-neo monitor --live live.csv"),
}


def _rows(*reports: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rep in reports:
        for row in (rep or {}).get("checks", []):
            if row.get("status") != "skip":
                out.setdefault(row["id"], row)
    return out


def _alternative(alt: tuple[tuple[str, tuple[str, ...]], ...], rows: dict[str, dict[str, Any]]) -> str:
    """``met``, ``failed`` (present but not allowed) or ``absent`` (some evidence missing)."""
    if any(cid not in rows for cid, _ in alt):
        return "absent"
    return "met" if all(rows[cid]["status"] in allowed for cid, allowed in alt) else "failed"


def readiness(
    certificate: dict[str, Any] | None = None, alpha: dict[str, Any] | None = None, live: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The Alpha Readiness Level of the evidence given.

    Args:
        certificate: A ``strategy-verdict/1`` certificate of the strategy.
        alpha: An ``alpha-report/1`` of its signal.
        live: A ``live-monitor/1`` report after launch.

    Returns:
        ``{"schema", "level", "of", "levels": [{level, name, state, blocking}], "summary", "next_step", "disclaimer"}``
        where ``state`` is ``met``, ``failed`` or ``not assessed``.
    """
    rows = _rows(certificate, alpha, live)
    lookahead_fails = sorted(r["id"] for r in rows.values() if r.get("category") == "lookahead" and r["status"] == "fail")
    levels, level, stopped = [], 0, False
    for n, (name, requirements, how) in LEVELS.items():
        state, blocking = "met", []
        for alternatives in requirements:
            results = [_alternative(a, rows) for a in alternatives]
            if "met" in results:
                continue
            ids = sorted({cid for a in alternatives for cid, _ in a})
            if "failed" in results:
                state = "failed"
                blocking += [i for i in ids if i in rows and rows[i]["status"] not in OK]
            elif state != "failed":
                state = "not assessed"
                blocking += [f"{i} (not run)" for i in ids if i not in rows][:3]
        if n == 2 and lookahead_fails:
            state, blocking = "failed", lookahead_fails
        levels.append({"level": n, "name": name, "state": state, "blocking": blocking, "how": how})
        if state == "met" and not stopped:
            level = n
        else:
            stopped = True
    nxt = next((x for x in levels if x["state"] != "met"), None)
    if nxt is None:
        summary = "ARL 9/9: every level is met by the evidence given"
    else:
        reason = ", ".join(nxt["blocking"][:3]) or "no evidence"
        verb = "blocked at" if nxt["state"] == "failed" else "not assessed beyond"
        where = nxt["level"] if nxt["state"] == "failed" else nxt["level"] - 1
        summary = f"ARL {level}/9 — {verb} {where}: {nxt['name'].lower()} ({reason})"
    return {
        "schema": READINESS_SCHEMA_ID, "level": level, "of": 9, "levels": levels, "summary": summary,
        "next_step": None if nxt is None else (nxt["how"] if nxt["state"] == "not assessed" else f"fix: {', '.join(nxt['blocking'][:3])}"),
        "disclaimer": f"Rates the evidence, not the investment. {disclaimer.SHORT}",
    }


__all__ = ["LEVELS", "READINESS_SCHEMA_ID", "readiness"]
