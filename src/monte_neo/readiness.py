"""Alpha Readiness Level (ARL 1-9) and its depth (0-4 per level): one line a research committee can read.

The Alpha Readiness Level (ARL) was devised by Rostyslav Shcherbyna, author of Monte-Neo; it is modelled on the idea of a
technology readiness level and is a Monte-Neo scale, not an industry standard.

Like a technology readiness level, each level asks for evidence that the level below cannot give. The level is the
highest one whose requirements, and those of every level below it, are met. A level whose evidence was not produced is
**not assessed**, never passed: the report then names the run that would assess it (for example ``--aum`` or ``--book``).
Every level also has a **depth** from 0 to 4 (see :mod:`monte_neo.arl_depth`); a depth never lifts the level.

All numbers and rules are read from ``arl_rules_v2.json`` (:mod:`monte_neo.arl_rules`), the single source of truth; the
report records the rules version and that it is ``provisional`` until the owner freezes it.

Evidence comes from a ``strategy-verdict/1`` certificate, an ``alpha-report/1``, a ``live-monitor/1`` report and a
sealed holdout record, as check rows. A requirement is a list of alternatives; one alternative is met when all of its
checks are present (not skipped) with an allowed status. Level 2 also fails on any failed look-ahead check, whichever
produced it (the level is then at most 1). The ``caps`` of the rules apply too: a survivorship warning caps the level
at 4, a non-significant ``alpha_after_beta`` blocks level 5, and paper, testnet or simulated live data caps it at 8.

The ARL rates the **evidence**, not the investment: an ARL of 7 is not a recommendation to trade.
"""

from __future__ import annotations

from typing import Any

from monte_neo import disclaimer
from monte_neo.arl_depth import MET, Evidence, depth_for_level
from monte_neo.arl_rules import load_rules

READINESS_SCHEMA_ID = "alpha-readiness/1"
_STATUS = load_rules()["statuses"]
OK = tuple(_STATUS["OK"])
SOFT = tuple(_STATUS["SOFT"])


def _compat() -> tuple[dict[int, Any], dict[str, tuple[int, str]]]:
    r = load_rules()
    levels = {lv["level"]: (lv["name"], [[tuple((cid, tuple(_STATUS[s])) for cid, s in alt) for alt in alts] for alts in lv["requirements"]], lv["how"])
              for lv in r["levels"]}
    return levels, {c["check"]: (c["max_level"], c["why"]) for c in r["caps"]["ceilings"]}


# level: (name, requirements, how to produce the evidence), and check id -> (highest ARL while it warns or fails, why):
# derived from the rules file for callers that import them.
LEVELS, CEILINGS = _compat()


def _rows(*reports: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rep in reports:
        for row in (rep or {}).get("checks", []):
            if row.get("status") != "skip":
                out.setdefault(row["id"], row)
    return out


def _alternative(alt: Any, rows: dict[str, dict[str, Any]]) -> str:
    """``met``, ``failed`` (present but not allowed) or ``absent`` (some evidence missing)."""
    if any(cid not in rows for cid, _ in alt):
        return "absent"
    return "met" if all(rows[cid]["status"] in allowed for cid, allowed in alt) else "failed"


def _project_trials(n_trials: int | None, certificate: dict[str, Any] | None, alpha: dict[str, Any] | None, rows: dict[str, Any]) -> int:
    seen = [int(n_trials or 1)]
    if certificate:
        seen.append(int((certificate.get("reproducibility") or {}).get("n_trials") or 1))
    if alpha:
        seen.append(int(((alpha.get("reproducibility") or {}).get("settings") or {}).get("n_trials") or 1))
    if "trial_ledger" in rows:
        seen.append(int((rows["trial_ledger"].get("details") or {}).get("counted") or 1))
    return max(seen)


def _derived(
    rules: dict[str, Any], certificate: dict[str, Any] | None, alpha: dict[str, Any] | None, rows: dict[str, Any], trials: int
) -> None:
    """Rows the rules derive from a metric (``derived``), for example a Deflated Sharpe floor at level 4.

    The metric is read from the certificate, else from the check row of the same name (an alpha report on net returns).
    A metric computed with fewer trials than the project tried overstates the evidence, so the row warns.
    Without the metric there is no row: the level is then not assessed, never passed.
    """
    metrics = (certificate or {}).get("metrics") or {}
    for dv in rules.get("derived", []):
        if dv["id"] in rows:
            continue
        value = metrics.get(dv["metric"])
        if value is not None:
            cert_trials = int(((certificate or {}).get("reproducibility") or {}).get("n_trials") or 1)
        else:
            value = ((rows.get(dv["metric"]) or {}).get("details") or {}).get(dv["metric"])
            settings = ((alpha or {}).get("reproducibility") or {}).get("settings") or {}
            cert_trials = int((rows.get(dv["metric"]) or {}).get("details", {}).get("n_trials") or settings.get("n_trials") or 1)
        if value is None:
            continue
        value = float(value)
        if cert_trials < trials:
            status, summary = "warn", f"{dv['metric']} {value:.3f} was computed with {cert_trials} trials, the project tried {trials}: verify again with --n-trials {trials}"
        elif value >= float(dv["min"]):
            status, summary = "pass", f"{dv['metric']} {value:.3f} >= {dv['min']}"
        else:
            status, summary = "fail", f"{dv['metric']} {value:.3f} < {dv['min']}: {dv['next_action']}"
        rows[dv["id"]] = {"id": dv["id"], "category": dv.get("category", "statistics"), "status": status, "summary": summary,
                          "details": {"metric": dv["metric"], "value": value, "min": dv["min"], "trials": cert_trials, "why": dv["why"]}}


def _trials_evidenced(rows: dict[str, dict[str, Any]], accepts: list[str]) -> bool:
    """True when the number of variants tried is backed by a record, not only by the n_trials the caller typed."""
    led = rows.get("trial_ledger")
    if "trial_ledger" in accepts and led:
        chain_ok = (led.get("details") or {}).get("chain_ok")
        if chain_ok is True or (chain_ok is None and led["status"] in ("pass", "warn")):  # an edited ledger is not evidence
            return True
    imp = rows.get("trials_imported")
    if "trials_imported" in accepts and imp and imp["status"] in ("pass", "warn"):
        return True
    reg = (rows.get("preregistration") or {}).get("details") or {}
    if "preregistration" in accepts and reg.get("found") and reg.get("same_code") and reg.get("before_first_verification"):
        return True
    hyg = (rows.get("research_hygiene") or {}).get("details") or {}
    missing = hyg.get("missing") or []
    return "research_hygiene" in accepts and bool(hyg) and ("trial_ledger" not in missing or "registered_before_first_run" not in missing)


def readiness(
    certificate: dict[str, Any] | None = None, alpha: dict[str, Any] | None = None, live: dict[str, Any] | None = None, *,
    holdout: dict[str, Any] | None = None, n_trials: int | None = None, evidence: dict[str, Any] | None = None,
    rules_version: str | None = None,
) -> dict[str, Any]:
    """The Alpha Readiness Level of the evidence given, with the depth of every level.

    Args:
        certificate: A ``strategy-verdict/1`` certificate of the strategy.
        alpha: An ``alpha-report/1`` of its signal.
        live: A ``live-monitor/1`` report after launch.
        holdout: A sealed-holdout record (:meth:`monte_neo.verify.sealed_holdout.SealedHoldout.evidence`).
        n_trials: Every variant tried in the whole project; levels 4-6 are computed with at least this many.
        evidence: Extra named evidence (for example ``{"fresh_fetch_hash": True}``) for criteria no check produces yet.
        rules_version: Compute with this recorded version of the rules (default: the current one).

    Returns:
        ``{"schema", "rules_version", "provisional", "level", "of", "depth", "headline", "levels", "summary", "next_step",
        "next_actions", "ceilings", "disclaimer", "authorship"}``. ``levels`` holds, per level, ``state`` (``met``, ``failed``,
        ``capped`` or ``not assessed``), ``blocking``, ``depth`` (0 unless the level is reached, ``counts``), ``depth_if_reached`` and
        ``depth_criteria``. ``headline`` reads ``ARL 6, depth 3/4``.
    """
    rules = load_rules(rules_version)
    rows = _rows(certificate, alpha, live)
    _derived(rules, certificate, alpha, rows, _project_trials(n_trials, certificate, alpha, rows))
    caps = rules["caps"]
    lookahead_fails = sorted(r["id"] for r in rows.values() if r.get("category") == "lookahead" and r["status"] == "fail")
    levels, level, stopped = [], 0, False
    for lv in rules["levels"]:
        n = lv["level"]
        state, blocking = "met", []
        for alternatives in lv["requirements"]:
            results = [_alternative([(cid, tuple(_STATUS[s])) for cid, s in a], rows) for a in alternatives]
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
        hits = [b["check"] for b in caps["blockers"] if n == b["level"] and b["check"] in rows and rows[b["check"]]["status"] not in OK]
        if hits:  # a check that ran and warned blocks the level, e.g. the return is not more than benchmark exposure
            state, blocking = "failed", hits
        levels.append({"level": n, "name": lv["name"], "state": state, "blocking": blocking, "how": lv["how"]})
        if state == "met" and not stopped:
            level = n
        else:
            stopped = True
    capped = sorted((c["check"], c["max_level"], c["why"]) for c in caps["ceilings"] if c["check"] in rows and rows[c["check"]]["status"] in ("warn", "fail"))
    te = caps.get("trial_evidence")
    if te and not _trials_evidenced(rows, te["accepts"]):
        capped.append(("trial_evidence", te["max_level"], te["why"]))
    live_src = ((live or {}).get("metrics") or {}).get("source")
    ns = caps["non_real_sources"]
    if live and live_src != "real_fills" and (live_src in ns["sources"] or live_src is None):
        capped.append(("live_source", ns["max_level"], ns["why"]))
    cap = min((c[1] for c in capped), default=None)
    if cap is not None:
        level = min(level, cap)
        for lv in levels:
            if lv["level"] > cap and lv["state"] == "met":
                lv["state"], lv["blocking"] = "capped", [c for c, m, _ in capped if m <= cap]
    nxt = next((x for x in levels if x["state"] != "met"), None)
    live_note = rows["live_source"]["summary"] if nxt and nxt["level"] == 9 and "live_source" in rows and rows["live_source"]["status"] not in OK else ""
    if nxt is None:
        summary = "ARL 9/9: every level is met by the evidence given"
    elif nxt["state"] == "capped":
        cid, _, why = next(c for c in capped if c[1] <= cap)
        summary = f"ARL {level}/9 — capped at {cap}: {cid} ({why})"
    else:
        reason = ", ".join(nxt["blocking"][:3]) or "no evidence"
        verb = "blocked at" if nxt["state"] == "failed" else "not assessed beyond"
        where = nxt["level"] if nxt["state"] == "failed" else nxt["level"] - 1
        summary = f"ARL {level}/9 — {verb} {where}: {nxt['name'].lower()} ({reason})" + (f". {live_note}" if live_note else "")
    ev = Evidence(
        rows, holdout=holdout, n_trials=_project_trials(n_trials, certificate, alpha, rows), extra=evidence,
        metrics={"cert": (certificate or {}).get("metrics") or {}, "alpha": (alpha or {}).get("metrics") or {}, "live": (live or {}).get("metrics") or {}},
    )
    actions: list[dict[str, Any]] = []
    for lv in levels:
        d = depth_for_level(lv["level"], ev, rules)
        lv["counts"] = lv["level"] <= level and lv["state"] == "met"
        lv["depth_if_reached"], lv["depth_criteria"] = d["depth"], d["criteria"]  # what the criteria say if the level were reached
        lv["depth"] = d["depth"] if lv["counts"] else 0  # a level that is not reached has depth 0: depth never skips a level
        if lv["level"] in (level, level + 1) and lv["level"] >= 1:
            actions += [{"level": lv["level"], "criterion": c["id"], "state": c["state"], "why": c["why"], "command": c["needs"],
                         "repair_check": c["repair"]} for c in d["criteria"] if c["state"] != MET]
    depth = next((lv["depth"] for lv in levels if lv["level"] == level), 0) if level else 0
    return {
        "schema": READINESS_SCHEMA_ID, "rules_version": rules["version"], "provisional": rules["status"] == "provisional",
        "level": level, "of": 9, "depth": depth,
        "headline": f"ARL {level}, depth {depth}/4 ({rules['version']}{', provisional' if rules['status'] == 'provisional' else ''})",
        "levels": levels, "summary": summary,
        "next_step": None if nxt is None else (nxt["how"] if nxt["state"] == "not assessed" else f"fix: {', '.join(nxt['blocking'][:3])}"),
        "next_actions": actions, "n_trials_used": ev.n_trials,
        "ceilings": [{"check": c, "max_level": m, "why": w} for c, m, w in capped],
        "authorship": rules["authorship"],
        "disclaimer": f"Rates the evidence, not the investment. {disclaimer.SHORT}",
    }


def arl_block(readiness_report: dict[str, Any]) -> dict[str, Any]:
    """The compact ``arl`` block written into certificates: level, depth, rules version, provisional flag, open criteria."""
    r = readiness_report
    return {"level": r["level"], "depth": r["depth"], "headline": r["headline"], "rules_version": r["rules_version"],
            "provisional": r["provisional"], "summary": r["summary"],
            "open_criteria": [f"L{a['level']} {a['criterion']}: {a['state']}" for a in r["next_actions"]][:12]}


__all__ = ["CEILINGS", "LEVELS", "READINESS_SCHEMA_ID", "arl_block", "readiness"]
