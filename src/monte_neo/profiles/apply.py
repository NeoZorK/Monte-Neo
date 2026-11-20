"""The ``profile`` block of a certificate: coverage of the profile's required checks."""

from __future__ import annotations

from typing import Any

from monte_neo.profiles.registry import RULES_VERSION, get_profile

NOTE = "A profile reports coverage; it never raises a verdict. Not investment advice."


def profile_block(profile_id: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Which required checks ran, which did not (with the reason), which failed, and what is not assessed."""
    p = get_profile(profile_id)
    by_id = {c["id"]: c for c in checks}
    ran: list[str] = []
    failed: list[str] = []
    not_run: list[dict[str, str]] = []
    for cid in p["required_checks"]:
        row = by_id.get(cid)
        if row is None:
            not_run.append({"check": cid, "why": "not produced for this input type"})
        elif row["status"] == "skip":
            not_run.append({"check": cid, "why": str(row.get("summary", "skipped"))})
        else:
            ran.append(cid)
            if row["status"] == "fail":
                failed.append(cid)
    recommended_missing = [c for c in p.get("recommended_checks", []) if c not in by_id or by_id[c]["status"] == "skip"]
    return {
        "id": p["id"], "rules": RULES_VERSION, "title": p["title"], "benchmark": p["benchmark"],
        "required": list(p["required_checks"]), "ran": ran, "failed": failed, "not_run": not_run,
        "complete": not not_run, "recommended_not_run": recommended_missing,
        "metrics_focus": list(p["metrics_focus"]), "not_assessed": list(p["not_assessed"]), "note": NOTE,
    }
