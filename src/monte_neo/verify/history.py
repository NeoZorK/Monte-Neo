"""Certificate history and the difference between two certificates.

A repository that verifies its strategies on every commit gets a chain of certificates. ``diff_certificates``
says what changed between two of them (verdict, metrics, checks), and ``History`` keeps the chain in
``.monte-neo/history.jsonl`` so that a pull request can be blocked when the verdict got worse.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from monte_neo.verify.chainlog import ChainLog

DEFAULT_PATH = Path(".monte-neo") / "history.jsonl"
VERDICT_RANK = {"PASS": 0, "PASS_WITH_WARNINGS": 1, "NEEDS_MORE_EVIDENCE": 2, "REJECT": 3}
STATUS_RANK = {"pass": 0, "info": 0, "skip": 0, "warn": 1, "fail": 2}
METRICS = (
    "total_return", "max_drawdown", "sharpe_annualized", "psr", "deflated_sharpe", "n_closed_trades", "breakeven_cost_bps",
    "exposure", "capacity_5pct",
)


def _metric(report: dict[str, Any], key: str) -> float | None:
    value = (report.get("metrics") or {}).get(key)
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    """The part of a certificate that history keeps."""
    trials = (report.get("reproducibility") or {}).get("n_trials")
    return {
        "certificate": report.get("certificate_id"),
        "verdict": report.get("verdict"),
        "n_trials": trials,
        "metrics": {k: v for k in METRICS if (v := _metric(report, k)) is not None},
        "checks": {c["id"]: c["status"] for c in report.get("checks", [])},
    }


def diff_certificates(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """What changed from ``old`` to ``new`` (certificates or ``summarize`` outputs): verdict, metrics, checks, regression."""
    a = old if "checks" in old and isinstance(old["checks"], dict) else summarize(old)
    b = new if "checks" in new and isinstance(new["checks"], dict) else summarize(new)
    verdict_worse = VERDICT_RANK.get(b["verdict"], 0) > VERDICT_RANK.get(a["verdict"], 0)
    metrics = {}
    for key in sorted(set(a["metrics"]) | set(b["metrics"])):
        x, y = a["metrics"].get(key), b["metrics"].get(key)
        if x != y:
            metrics[key] = {"old": x, "new": y, "delta": None if x is None or y is None else round(y - x, 6)}
    checks = []
    for cid in sorted(set(a["checks"]) | set(b["checks"])):
        x, y = a["checks"].get(cid), b["checks"].get(cid)
        if x != y:
            worse = STATUS_RANK.get(y or "pass", 0) > STATUS_RANK.get(x or "pass", 0)
            checks.append({"id": cid, "old": x, "new": y, "worse": worse})
    newly_failing = [c["id"] for c in checks if c["new"] == "fail"]
    return {
        "same_certificate": a["certificate"] == b["certificate"],
        "verdict": {"old": a["verdict"], "new": b["verdict"], "worse": verdict_worse},
        "n_trials": {"old": a["n_trials"], "new": b["n_trials"]},
        "metrics": metrics,
        "checks": checks,
        "regression": bool(verdict_worse or newly_failing),
        "newly_failing": newly_failing,
    }


def render_markdown(diff: dict[str, Any]) -> str:
    """The diff as a pull-request comment."""
    v = diff["verdict"]
    head = "Verdict **regressed**" if diff["regression"] else "No regression"
    lines = [f"### Monte-Neo: {head}", "", f"Verdict: `{v['old']}` -> `{v['new']}`" + ("" if not diff["same_certificate"] else " (same certificate)"), ""]
    if diff["metrics"]:
        lines += ["| Metric | Before | After |", "|---|---|---|"]
        lines += [f"| {k} | {m['old']} | {m['new']} |" for k, m in diff["metrics"].items()]
        lines.append("")
    if diff["checks"]:
        lines += ["| Check | Before | After |", "|---|---|---|"]
        lines += [f"| {c['id']} | {c['old'] or '-'} | {c['new'] or '-'}{' (worse)' if c['worse'] else ''} |" for c in diff["checks"]]
    return "\n".join(lines) + "\n"


class History:
    """The chain of certificate summaries of one project."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.log = ChainLog(path or DEFAULT_PATH)

    def add(self, report: dict[str, Any], *, label: str | None = None, commit: str | None = None) -> dict[str, Any]:
        return self.log.append({"label": label, "commit": commit, **summarize(report)})

    def latest(self, label: str | None = None) -> dict[str, Any] | None:
        rows = [e for e in self.log.entries() if label is None or e.get("label") == label]
        return rows[-1] if rows else None

    def compare(self, report: dict[str, Any], label: str | None = None) -> dict[str, Any] | None:
        """Diff of ``report`` against the latest entry (``None`` when the history is empty)."""
        last = self.latest(label)
        return None if last is None else diff_certificates(last, report)


__all__ = ["DEFAULT_PATH", "History", "diff_certificates", "render_markdown", "summarize"]
