"""Maps from model-risk and algorithm-testing frameworks to the evidence a certificate holds.

Each clause names the check categories or check ids that are evidence for it and whether a person must still judge it.
Coverage is about **evidence**, not compliance: a clause is ``covered`` when every evidence item was checked,
``partial`` when some was, or when the clause needs a human judgement the verifier cannot make, and ``not covered``
otherwise. A dossier never claims that a firm complies with a framework.
"""

from __future__ import annotations

from typing import Any

# (clause, what it asks, evidence: categories ("cat:...") or check ids, needs a human judgement)
Clause = tuple[str, str, tuple[str, ...], bool]

FRAMEWORKS: dict[str, dict[str, Any]] = {
    "generic": {
        "title": "Generic validation checklist",
        "clauses": [
            ("Data", "Data is complete, ordered and free of defects that create profit", ("cat:integrity",), False),
            ("Look-ahead", "No information from the future reaches a decision", ("cat:lookahead",), False),
            ("Economics", "The result survives costs, delays and capacity", ("cat:economics",), False),
            ("Statistics", "The result is significant after the variants tried", ("cat:statistics",), False),
            ("Claims", "Reported numbers match the verified ones", ("claim_consistency",), False),
            ("Policy", "The institution's thresholds are met", ("policy",), False),
            ("Reproducibility", "Anyone can rerun the test from the same inputs", ("repro",), False),
            ("Monitoring", "Live behaviour is compared with the backtest after launch", ("live",), False),
        ],
    },
    "sr11-7": {
        "title": "Federal Reserve SR 11-7 / OCC 2011-12, Supervisory Guidance on Model Risk Management",
        "clauses": [
            ("Conceptual soundness", "Design, theory and logic of the model are sound", ("cat:lookahead", "cat:integrity"), True),
            ("Data quality and relevance", "Data are suitable and their limitations are understood", ("cat:integrity",), False),
            ("Outcomes analysis and back-testing", "Model outputs are compared with outcomes", ("cat:economics", "cat:statistics"), False),
            ("Sensitivity analysis", "Results are tested under changed inputs and assumptions", ("delay_sensitivity", "cost_margin"), False),
            ("Assumptions and limitations", "They are identified and documented", ("limitations",), False),
            ("Effective challenge", "Independent, competent review that can be reproduced", ("repro",), True),
            ("Ongoing monitoring", "Performance is monitored after implementation", ("live",), False),
            ("Governance, policies and controls", "Limits and policies are defined and applied", ("policy",), True),
            ("Documentation", "Enough detail for a third party to understand the model", ("limitations", "repro"), False),
        ],
    },
    "ss1-23": {
        "title": "PRA SS1/23, Model risk management principles for banks",
        "clauses": [
            ("Principle 1: model identification and classification", "The model is inventoried and tiered", ("policy",), True),
            ("Principle 2: governance", "Policies, roles and limits are set", ("policy",), True),
            ("Principle 3: development, implementation and use", "Testing of data, methodology and performance", ("cat:integrity", "cat:lookahead", "cat:economics", "cat:statistics"), False),
            ("Principle 4: independent validation", "Independent review, reproducible results", ("repro",), True),
            ("Principle 5: model risk mitigants", "Limitations known; adjustments and monitoring in place", ("limitations", "live"), True),
        ],
    },
    "rts6": {
        "title": "MiFID II, Commission Delegated Regulation (EU) 2017/589 (RTS 6), testing of algorithms",
        "clauses": [
            ("Art. 5: testing before deployment", "The algorithm behaves as intended, also under stressed conditions", ("cat:lookahead", "cat:economics", "delay_sensitivity"), False),
            ("Art. 5: data and market conditions", "Testing covers the data and conditions the algorithm will meet", ("cat:integrity", "data_quality"), True),
            ("Art. 6: conformance testing with venues", "Tested against the venue's systems", ("venue",), True),
            ("Art. 7: testing environments", "Separate environment for testing", ("repro",), True),
            ("Art. 9: annual self-assessment", "Yearly review of algorithmic trading", ("live",), True),
        ],
    },
    "crypto": {
        "title": "Crypto fund and desk checklist (a self-check list, not a regulation)",
        "clauses": [
            ("24/7 data gaps", "Outages and missing bars in a market that never closes are found", ("data_quality", "quote_quality"), False),
            ("Funding and carry costs", "Perpetual funding, borrow and fees are in the cost model and the result survives more", ("cost_margin", "spread_cost"), False),
            ("Exchange and venue latency", "Profit survives the real arrival time of quotes", ("latency_tolerance", "latency_monte_carlo", "delay_sensitivity"), False),
            ("Liquidity and capacity", "Size can be traded without moving the price", ("capacity", "market_impact", "participation_limit"), False),
            ("Survivorship of delisted tokens", "Dead and delisted tokens are in the test universe", ("survivorship",), False),
            ("Stablecoin and market-wide crash stress", "The strategy is replayed through depegs and crashes", ("historical_stress_replay", "tail_risk"), False),
            ("Custody, counterparty and exchange risk", "Who holds the assets and what happens if a venue fails", ("policy",), True),
        ],
    },
    "academic": {
        "title": "Academic appendix checklist for a backtest-based paper (a self-check list, not a journal rule)",
        "clauses": [
            ("Pre-registration", "The hypothesis was fixed before the data were looked at", ("preregistration",), False),
            ("Trials disclosed and Sharpe deflated", "The number of variants tried is stated and the Sharpe is deflated for it", ("trial_ledger", "deflated_sharpe"), False),
            ("Out-of-sample or holdout", "Results are shown on data that did not choose the strategy", ("walk_forward_oos",), False),
            ("Multiple-testing hurdle", "The t-statistic clears a hurdle for the whole search", ("hlz_hurdle",), False),
            ("Reproducibility", "A certificate and a recheck let a reader rerun the test", ("repro",), False),
            ("Data availability", "Readers can obtain the data or a faithful substitute", ("limitations",), True),
            ("Code availability", "Readers can obtain the code that produced the signals", ("limitations",), True),
        ],
    },
}


def _evidence_rows(item: str, report: dict[str, Any], live: bool) -> tuple[bool, list[dict[str, Any]]]:
    checks = report.get("checks", [])
    if item == "repro":
        return bool(report.get("certificate_id") and report.get("reproducibility")), []
    if item == "limitations":
        return True, []  # the dossier always writes the limitations section
    if item == "live":
        return live, []
    if item == "venue":
        return False, []
    if item.startswith("cat:"):
        rows = [c for c in checks if c.get("category") == item[4:] and c.get("status") != "skip"]
    else:
        rows = [c for c in checks if c.get("id") == item and c.get("status") != "skip"]
    return bool(rows), rows


def framework_map(report: dict[str, Any], framework: str, live: bool = False) -> dict[str, Any]:
    """Clause-by-clause coverage of one framework by a certificate.

    Args:
        report: A ``strategy-verdict/1`` certificate.
        framework: One of :data:`FRAMEWORKS`.
        live: Whether a live-monitoring report is attached.

    Returns:
        ``{"framework", "title", "clauses": [{clause, asks, coverage, result, evidence, human_judgement}]}``.
    """
    if framework not in FRAMEWORKS:
        raise ValueError(f"unknown framework {framework!r}; known: {', '.join(FRAMEWORKS)}")
    spec = FRAMEWORKS[framework]
    out = []
    for name, asks, evidence, human in spec["clauses"]:
        found = [_evidence_rows(item, report, live) for item in evidence]
        present = sum(1 for ok, _ in found if ok)
        rows = [r for _, rs in found for r in rs]
        coverage = "not covered" if present == 0 else ("covered" if present == len(evidence) and not human else "partial")
        statuses = {r["status"] for r in rows}
        result = "fail" if "fail" in statuses else "warn" if "warn" in statuses else ("pass" if present else "—")
        out.append({
            "clause": name, "asks": asks, "coverage": coverage, "result": result, "human_judgement": human,
            "evidence": sorted({r["id"] for r in rows}) or [e for e, (ok, _) in zip(evidence, found, strict=True) if ok],
        })
    return {"framework": framework, "title": spec["title"], "clauses": out}


__all__ = ["FRAMEWORKS", "framework_map"]
