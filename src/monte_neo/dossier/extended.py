"""The extended dossier: several certificates, the search behind them, ARL and depth with reasons, and an evidence map.

``build_extended`` adds an ``extended`` section (``extended-dossier/1``) to a dossier. It is evidence for a validation,
not a statement of compliance: the clause map says which clause has which evidence in the dossier, nothing more.
"""

from __future__ import annotations

from typing import Any

from monte_neo.readiness import readiness

EXTENDED_SCHEMA_ID = "extended-dossier/1"
GROUPS = {
    "regimes": ("regime_stability", "regime_swap_null", "regime_mix_bootstrap", "time_reversal_null", "period_consistency"),
    "costs": ("costs_modeled", "cost_margin", "cost_sensitivity", "cost_realism", "spread_estimate", "delay_sensitivity"),
    "capacity": ("capacity", "execution_capacity", "liquidity_stress"),
}
EVIDENCE_STATEMENT = (
    "This is an evidence map: it lists which clause of a framework has which evidence in this dossier. It is not a compliance "
    "statement, a model approval or legal advice. Clauses that need human judgement are marked as such."
)


def _rows(cert: dict[str, Any], ids: tuple[str, ...]) -> list[dict[str, Any]]:
    by = {c["id"]: c for c in cert.get("checks", [])}
    return [{"id": i, "status": by[i]["status"], "summary": by[i]["summary"]} if i in by else {"id": i, "status": "not run", "summary": "not produced for this certificate"} for i in ids]


def _strategy(cert: dict[str, Any]) -> dict[str, Any]:
    r = readiness(certificate=cert)
    m = cert.get("metrics", {})
    levels = [{"level": x["level"], "name": x["name"], "state": x["state"], "blocking": x["blocking"],
               "depth": [{"id": d["id"], "name": d["name"], "state": d["state"], "why": d["why"]} for d in x.get("depth_criteria", [])]} for x in r["levels"]]
    return {
        "certificate_id": cert.get("certificate_id"), "verdict": cert.get("verdict"), "profile": (cert.get("profile") or {}).get("id"),
        "arl": {"level": r["level"], "depth": r["depth"], "headline": r["headline"], "rules": r["rules_version"], "provisional": r["provisional"], "next_step": r.get("next_step")},
        "levels": levels,
        "metrics": {k: m.get(k) for k in ("total_return", "sharpe_annualized", "deflated_sharpe", "max_drawdown", "breakeven_cost_bps", "n_closed_trades") if m.get(k) is not None},
        "n_trials": (cert.get("reproducibility") or {}).get("n_trials"),
        "periods": [{"period": p["period"], "return": p["return"]} for p in (cert.get("breakdown") or {}).get("periods", [])[:24]],
        **{name: _rows(cert, ids) for name, ids in GROUPS.items()},
    }


def build_extended(
    certs: list[dict[str, Any]], *, funnel: dict[str, Any] | None = None, portfolio: dict[str, Any] | None = None,
    live: dict[str, Any] | None = None, framework: str = "sr11-7",
) -> dict[str, Any]:
    """The ``extended`` section for ``certs`` (at least one). ``funnel``, ``portfolio`` and ``live`` are optional reports."""
    if not certs:
        raise ValueError("an extended dossier needs at least one certificate")
    from monte_neo.dossier.frameworks import framework_map

    strategies = [_strategy(c) for c in certs]
    trials = [s["n_trials"] or 1 for s in strategies]
    search = {
        "certificates": len(certs), "n_trials_declared": trials, "n_trials_max": max(trials),
        "verdicts": {v: sum(1 for c in certs if c.get("verdict") == v) for v in sorted({str(c.get("verdict")) for c in certs})},
        "funnel": funnel, "search_cost": (funnel or {}).get("search_cost"),
        "note": "Every variant tried counts: the Deflated Sharpe in each certificate prices this search." if funnel else "No research project was given: only the trial counts declared in the certificates are shown.",
    }
    provided = {"strategies": True, "search funnel": funnel is not None, "portfolio": portfolio is not None, "monitoring": live is not None}
    return {
        "schema": EXTENDED_SCHEMA_ID, "strategies": strategies, "search": search,
        "portfolio": ({"verdict": portfolio.get("verdict"), "checks": [{"id": c["id"], "status": c["status"], "summary": c["summary"]} for c in portfolio.get("checks", [])]} if portfolio else None),
        "monitoring": ({"verdict": live.get("verdict"), "checks": [{"id": c["id"], "status": c["status"], "summary": c["summary"]} for c in live.get("checks", [])]} if live else None),
        "evidence_map": {"statement": EVIDENCE_STATEMENT, **framework_map(certs[0], framework, live=live is not None)},
        "sections_provided": provided, "not_provided": [k for k, v in provided.items() if not v],
    }


__all__ = ["EVIDENCE_STATEMENT", "EXTENDED_SCHEMA_ID", "build_extended"]
