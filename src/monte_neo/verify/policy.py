"""Risk policy as code: an institution's own thresholds, written once in a TOML file and recorded in every certificate.

The verifier's defaults are a sensible floor. A fund, a bank's model-validation team or a prop desk has its own: at
least 100 trades, a Deflated Sharpe of 0.95, no warnings at all, costs stressed twice. A policy file states them, the
verdict says which rule was breached, and the policy itself (with its hash) goes into the certificate, so a recheck
applies the same rules and a reader sees which rules the result was judged by.

Example (``monte-neo policy init`` writes a commented template)::

    [policy]
    name = "model-risk-strict"
    version = "2026-10"
    owner = "Model Risk Management"
    on_breach = "reject"          # or "needs_more_evidence"

    [inputs]                      # applied before the run
    min_trades = 100
    cost_multiplier = 2.0         # commission and slippage times this

    [rules]                       # applied to the result
    allow_warnings = false
    min_deflated_sharpe = 0.95
    min_sharpe = 0.5
    max_drawdown = 0.25           # fraction of equity
    required_checks = ["lookahead_truncation", "net_profitability"]
    fail_on_warn = ["implausible_performance", "period_consistency"]
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

from monte_neo.verify.checks import check

POLICY_SCHEMA_ID = "verifier-policy/1"
SECTIONS = {
    "policy": {"name": str, "version": str, "owner": str, "on_breach": str, "tier": int, "description": str},
    "inputs": {"min_trades": int, "cost_multiplier": float},
    "rules": {
        "allow_warnings": bool,
        "min_deflated_sharpe": float,
        "min_sharpe": float,
        "max_drawdown": float,
        "required_checks": list,
        "fail_on_warn": list,
    },
}
ON_BREACH = ("reject", "needs_more_evidence")

TEMPLATE = '''# Monte-Neo verifier policy: your institution's thresholds (TOML). Recorded in every certificate.
[policy]
name = "my-policy"
version = "1"
owner = "Research"
on_breach = "reject"            # "reject" or "needs_more_evidence"

[inputs]                        # applied before the run
min_trades = 50                 # closed trades needed for statistics
cost_multiplier = 1.0           # commission and slippage are multiplied by this (2.0 = stress costs twice)

[rules]                         # applied to the result
allow_warnings = true           # false: any warning breaches the policy
min_deflated_sharpe = 0.0       # 0.95 = the Sharpe survives the number of variants tried at 95 %
min_sharpe = 0.0                # annualised Sharpe after costs
max_drawdown = 1.0              # 0.25 = at most a 25 % drawdown
required_checks = []            # check ids that must run and pass, e.g. ["lookahead_truncation"]
fail_on_warn = []               # check ids whose warning counts as a breach
'''


def _validate(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for section, body in raw.items():
        if section not in SECTIONS:
            raise ValueError(f"unknown policy section [{section}]; known: {', '.join(SECTIONS)}")
        if not isinstance(body, dict):
            raise ValueError(f"[{section}] must be a table")
        clean: dict[str, Any] = {}
        for key, value in body.items():
            kind = SECTIONS[section].get(key)
            if kind is None:
                raise ValueError(f"unknown key {key!r} in [{section}]; known: {', '.join(SECTIONS[section])}")
            if kind is float and isinstance(value, int) and not isinstance(value, bool):
                value = float(value)
            if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
                raise ValueError(f"[{section}] {key} must be {kind.__name__}, got {value!r}")
            if kind is list and not all(isinstance(v, str) for v in value):
                raise ValueError(f"[{section}] {key} must be a list of check ids")
            clean[key] = value
        out[section] = clean
    meta = out.setdefault("policy", {})
    if "name" not in meta:
        raise ValueError("[policy] name is required")
    if meta.setdefault("on_breach", "reject") not in ON_BREACH:
        raise ValueError(f"[policy] on_breach must be one of {ON_BREACH}")
    inputs = out.get("inputs", {})
    if inputs.get("min_trades", 1) < 1 or inputs.get("cost_multiplier", 1.0) <= 0:
        raise ValueError("[inputs] min_trades must be >= 1 and cost_multiplier > 0")
    return out


def load_policy(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    """Read and validate a policy (a TOML file, TOML text or an already parsed dict).

    Args:
        source: Path to a ``.toml`` file, TOML text, or a dict with ``policy`` / ``inputs`` / ``rules`` tables.

    Returns:
        The validated policy with ``schema`` and ``sha256`` (of its canonical JSON) added.

    Raises:
        ValueError: Unknown sections or keys, wrong types, missing name.
    """
    if isinstance(source, dict):
        raw = {k: v for k, v in source.items() if k not in ("schema", "sha256")}
    else:
        text = Path(source).read_text(encoding="utf-8") if Path(str(source)).suffix == ".toml" else str(source)
        try:
            raw = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"policy is not valid TOML: {exc}") from exc
    body = _validate(raw)
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"schema": POLICY_SCHEMA_ID, **body, "sha256": digest}


def run_inputs(policy: dict[str, Any] | None) -> dict[str, Any]:
    """Settings the policy fixes before the run: ``min_trades`` and ``cost_multiplier`` (absent keys are omitted)."""
    return dict((policy or {}).get("inputs", {}))


def _breaches(report: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    checks = {c["id"]: c for c in report.get("checks", [])}
    metrics = report.get("metrics", {})
    out: list[str] = []
    if not rules.get("allow_warnings", True):
        warned = sorted(i for i, c in checks.items() if c["status"] == "warn")
        if warned:
            out.append(f"warnings are not allowed: {', '.join(warned)}")
    for cid in rules.get("fail_on_warn", []):
        if checks.get(cid, {}).get("status") == "warn":
            out.append(f"{cid} warned, and the policy treats that as a breach")
    for cid in rules.get("required_checks", []):
        status = checks.get(cid, {}).get("status")
        if status not in ("pass", "info"):
            out.append(f"required check {cid} {'did not run' if status in (None, 'skip') else status + 'ed'}")
    limits = (
        ("min_deflated_sharpe", "deflated_sharpe", "Deflated Sharpe", lambda v, t: v >= t),
        ("min_sharpe", "sharpe_annualized", "annualised Sharpe", lambda v, t: v >= t),
        ("max_drawdown", "max_drawdown", "max drawdown", lambda v, t: abs(v) <= t),
    )
    for rule, metric, label, ok in limits:
        if rule in rules:
            value = metrics.get(metric)
            if value is None:
                out.append(f"{label} was not computed, so the policy limit {rules[rule]} cannot be confirmed")
            elif not ok(float(value), float(rules[rule])):
                out.append(f"{label} {float(value):.3f} breaches the policy limit {rules[rule]}")
    return out


def policy_row(report: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Check row ``policy``: which rules of the institution's policy the result breaches.

    A breach is a fail in category ``economics`` (``on_breach="reject"``: the verdict becomes REJECT) or
    ``statistics`` (``on_breach="needs_more_evidence"``).
    """
    meta = policy["policy"]
    found = _breaches(report, policy.get("rules", {}))
    details = {"name": meta["name"], "version": meta.get("version"), "sha256": policy["sha256"], "breaches": found}
    category = "economics" if meta["on_breach"] == "reject" else "statistics"
    label = f"policy {meta['name']}" + (f" v{meta['version']}" if meta.get("version") else "")
    if found:
        return check("policy", category, "fail", f"{label}: {len(found)} breach(es): {found[0]}", details)
    return check("policy", category, "pass", f"{label}: every rule is met", details)


def apply_policy(report: dict[str, Any], policy: str | Path | dict[str, Any]) -> dict[str, Any]:
    """Judge a finished ``strategy-verdict/1`` report by a policy and return the new report.

    Adds the ``policy`` check row, records the policy in ``reproducibility.policy`` (so a recheck applies the same
    rules) and recomputes the verdict, reasons, next actions and certificate id. A signature, if any, is dropped:
    the content changed, sign again.
    """
    from monte_neo.verify import checks as rows
    from monte_neo.verify.schema import aggregate_verdict, to_jsonable
    from monte_neo.verify.verdict import certificate_id

    rules = load_policy(policy)
    base = [c for c in report["checks"] if c["id"] != "policy"]
    row = policy_row({**report, "checks": base}, rules)
    checks = [*base, row]
    verdict = aggregate_verdict(checks)
    repro = {**report["reproducibility"], "policy": rules}
    out = {k: v for k, v in report.items() if k != "signature"}
    out.update(
        verdict=verdict,
        checks=checks,
        reproducibility=repro,
        certificate_id=certificate_id(repro, verdict),
        reasons=[f"{c['id']}: {c['summary']}" for s in ("fail", "warn") for c in checks if c["status"] == s],
        next_actions=rows.next_actions(checks),
    )
    result = to_jsonable(out)
    return type(report)(result) if type(report) is not dict else result


__all__ = ["POLICY_SCHEMA_ID", "TEMPLATE", "apply_policy", "load_policy", "policy_row", "run_inputs"]
