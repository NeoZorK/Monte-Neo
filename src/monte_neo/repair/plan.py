"""The repair catalogue: which defect gets which fixed, economically motivated repairs, and how a repaired file looks.

Repairs come from a small list declared here, with two or three values each, never from a search over returns. The ids
(R1...R14) follow the institutional roadmap so a reader can trace each one.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.repair import runtime

Step = tuple[str, dict[str, Any]]  # (transform name, parameters)

# defect check id -> (repair id, why, candidate step lists)
ECONOMIC_REPAIRS: dict[str, tuple[str, str, list[list[Step]]]] = {
    "net_profitability": ("R5", "costs and turnover eat the profit", [
        [("smooth", {"span": 5})], [("smooth", {"span": 20})], [("hold", {"bars": 5})], [("hold", {"bars": 20})]]),
    "cost_margin": ("R5", "the edge barely covers costs", [[("smooth", {"span": 10})], [("band", {"band": 0.25})]]),
    "delay_sensitivity": ("R5", "the profit lives in the next bar's fill", [[("hold", {"bars": 10})], [("smooth", {"span": 10})]]),
    "capacity": ("R9", "trades are large against the volume", [[("cap", {"cap": 0.1})], [("liquidity", {"quantile": 0.2})]]),
    "timing_significance": ("R8", "the profit is market exposure, not timing", [[("neutral", {})]]),
    "implausible_performance": ("R11", "risk is unstable", [[("voltarget", {"annual": 0.10, "span": 60})]]),
    "period_consistency": ("R11", "one period makes the profit", [[("voltarget", {"annual": 0.10, "span": 60})]]),
    "policy": ("R11", "the institution's limits are breached", [[("voltarget", {"annual": 0.10, "span": 60})], [("cap", {"cap": 0.5})]]),
}
REPAINT = {"repaint_history", "repaint_live"}
LOOKAHEAD = {"lookahead_truncation", "lookahead_perturbation", "lookahead_static_lint", "implausible_accuracy"}
# defects no transform can honestly repair, with what the person needs to do
NOT_REPAIRABLE: dict[str, str] = {
    "data_integrity": "fix the data (R13): broken bars are not a strategy defect",
    "data_quality": "check the flagged bars against another source (R13)",
    "survivorship": "a point-in-time universe is needed (R13: membership data)",
    "external_data": "the strategy reads files or the network the probes cannot see: pass the data in df",
    "determinism": "seed every random generator: a non-deterministic signal cannot be verified",
    "data_independence": "the strategy ignores its input (cached or precomputed answers): rewrite it",
    "ml_refit_gap": "the model's profit lives in fitting on the whole file (R4): use fit/predict and judge the walk-forward",
    "model_cutoff": "the edge exists only where the model may have seen the answers: use a model trained before the test",
    "pit_events": "join events by publication time in your pipeline",
}
TRANCHE: list[Step] = [("tranche", {"every": 21, "sleeves": 4})]


def candidates(checks: list[dict[str, Any]], rebalance_every: int | None = None, budget: int = 24) -> list[dict[str, Any]]:
    """Candidate repairs for the economic and robustness defects (each ``{"id", "why", "steps"}``), at most ``budget``."""
    out: list[dict[str, Any]] = []
    for row in checks:
        if row["status"] not in ("fail", "warn") or row["id"] not in ECONOMIC_REPAIRS:
            continue
        rid, why, options = ECONOMIC_REPAIRS[row["id"]]
        for steps in options:
            out.append({"id": rid, "for": row["id"], "why": why, "steps": steps})
    if rebalance_every:
        out.append({"id": "R7", "for": "rebalance_timing_luck", "why": "the result depends on the rebalance day",
                    "steps": [("tranche", {"every": int(rebalance_every), "sleeves": 4})]})
    seen, unique = set(), []
    for c in out:
        key = repr(c["steps"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    singles = unique[:budget]
    pairs = [{"id": f"{a['id']}+{b['id']}", "for": f"{a['for']}+{b['for']}", "why": f"{a['why']}; {b['why']}",
              "steps": a["steps"] + b["steps"]}
             for i, a in enumerate(singles) for b in singles[i + 1:] if a["steps"][0][0] != b["steps"][0][0]]
    return (singles + pairs)[:budget]


def apply_steps(fn: Callable[[pd.DataFrame], Any], steps: list[Step]) -> Callable[[pd.DataFrame], np.ndarray]:
    """``signal(df)`` that runs ``fn`` and then the transforms in order."""
    def repaired(df: pd.DataFrame) -> np.ndarray:
        pos = np.asarray(fn(df), dtype=float).reshape(-1)
        for name, params in steps:
            pos = runtime.TRANSFORMS[name](pos, df, **params)
        return pos

    return repaired


def _rename_signal(source: str, func: str) -> str:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func:
            node.name = "_mn_original_signal"
    return ast.unparse(tree)


def repaired_source(source: str, func: str, steps: list[Step], meta: dict[str, Any]) -> str:
    """A self-contained strategy file: the (causal) original renamed, the transforms it needs, and ``signal(df)``."""
    used = sorted({name for name, _ in steps})
    helpers = [inspect.getsource(runtime._mn_groups)] + [inspect.getsource(runtime.TRANSFORMS[n]) for n in used]
    calls = "\n".join(f"    pos = {runtime.TRANSFORMS[n].__name__}(pos, df{''.join(f', {k}={v!r}' for k, v in p.items())})" for n, p in steps)
    header = (
        f'"""Repaired by monte-neo repair {meta.get("version", "")} from {meta.get("name", "a strategy")} '
        f'(source sha256 {hashlib.sha256(source.encode()).hexdigest()[:16]}).\n\n'
        + "".join(f"- {r}\n" for r in meta.get("repairs", []))
        + '\nNot investment advice: a research example, not a call to trade or a promise of profit.\n"""\n\n'
    )
    body = _rename_signal(source, func)
    return (header + "import numpy as np\nimport pandas as pd\n\n" + body + "\n\n\n" + "\n\n".join(helpers)
            + "\n\ndef signal(df):\n    \"\"\"The original signal followed by the repairs, in order.\"\"\"\n"
            + "    pos = np.asarray(_mn_original_signal(df), dtype=float).reshape(-1)\n"
            + (calls + "\n" if calls else "") + "    return pos\n")


__all__ = ["ECONOMIC_REPAIRS", "LOOKAHEAD", "NOT_REPAIRABLE", "REPAINT", "TRANCHE", "apply_steps", "candidates", "repaired_source"]
