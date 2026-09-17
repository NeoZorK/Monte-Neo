"""Deterministic HeuristicPolicy — local research triage after export."""

from __future__ import annotations

from typing import Any

from monte_neo.policy.config import PolicyConfig
from monte_neo.policy.state import build_research_state


def _checklist_ok(checklist: dict[str, Any]) -> bool:
    if not checklist:
        return True
    critical = (
        "next_bar_fill",
        "fees",
        "no_lookahead",
        "cash_position_equity",
    )
    for key in critical:
        if key in checklist and checklist[key] is False:
            return False
    return True


def _top_cluster(top_rows: list[dict[str, Any]], cfg: PolicyConfig) -> bool:
    """True if several top rows share nearby fast/slow (not a lone spike)."""
    if len(top_rows) < 2:
        return False
    k = min(cfg.top_k, len(top_rows))
    head = top_rows[:k]
    f0 = int(head[0].get("fast", 0))
    s0 = int(head[0].get("slow", 0))
    near = 0
    for r in head[1:]:
        if abs(int(r.get("fast", 0)) - f0) <= cfg.cluster_fast_tol and abs(
            int(r.get("slow", 0)) - s0
        ) <= cfg.cluster_slow_tol:
            near += 1
    return near >= max(1, k // 3)


class HeuristicPolicy:
    """Rule-based research dispatcher (System-One *shape*, local rules)."""

    def __init__(self, config: PolicyConfig | None = None) -> None:
        self.config = config or PolicyConfig()

    def decide(self, state: dict[str, Any]) -> dict[str, Any]:
        cfg = self.config
        reasons: list[str] = []
        metrics = dict(state.get("metrics") or {})
        checklist = dict(state.get("checklist") or {})
        top_rows = list(state.get("top_rows") or [])
        best = metrics.get("best_return")
        frac_pos = metrics.get("frac_positive")
        edge = metrics.get("edge_best_minus_p50")
        std = metrics.get("std_return")

        overfit: str = "low"
        promote = False
        worth_mc = False
        next_action = "stop"
        confidence = cfg.confidence_floor

        if not state.get("ok", True):
            reasons.append("export ok=false")
            return self._pack("reject", False, False, "high", reasons, 0.95)

        if not _checklist_ok(checklist):
            reasons.append("critical work_checklist flag failed")
            return self._pack("export_golden", False, False, "high", reasons, 0.9)

        if best is None:
            reasons.append("no best_return in metrics")
            return self._pack("stop", False, False, "med", reasons, 0.7)

        best_f = float(best)
        if best_f < cfg.t_min_return:
            reasons.append(f"best_return {best_f:.4f} < t_min {cfg.t_min_return}")
            next_action = "reject"
            overfit = "med"
            confidence = 0.8
        elif frac_pos is not None and float(frac_pos) < cfg.p_min_frac_positive:
            reasons.append(
                f"frac_positive {float(frac_pos):.3f} < min {cfg.p_min_frac_positive}"
            )
            next_action = "stop"
            overfit = "med"
            confidence = 0.75
        else:
            clustered = _top_cluster(top_rows, cfg)
            if edge is not None and float(edge) > cfg.e_hi_edge and not clustered:
                overfit = "high"
                reasons.append(
                    f"lone peak: edge_best_minus_p50={float(edge):.4f} without top cluster"
                )
                worth_mc = True
                next_action = "run_mc"
                confidence = 0.7
            elif best_f >= cfg.t_promote_return and overfit != "high":
                promote = True
                worth_mc = True
                next_action = "promote_paper_oms"
                reasons.append(
                    f"best_return {best_f:.4f} >= promote threshold {cfg.t_promote_return}"
                )
                if clustered:
                    reasons.append("top parameter cluster present")
                confidence = 0.8
            elif clustered:
                next_action = "refine_grid"
                reasons.append("top rows form a parameter cluster — refine grid")
                confidence = 0.65
            else:
                next_action = "stop"
                reasons.append("decent but below promote threshold")
                confidence = 0.6

        if state.get("fallback_reason"):
            reasons.append(f"device fallback: {state['fallback_reason']}")

        # Optional holdout enrichment (from holdout_sma_sweep → ResearchState.metrics)
        h_gap = metrics.get("holdout_gap")
        h_over = metrics.get("holdout_overfit_risk")
        h_ok = metrics.get("holdout_promote_ok")
        if h_gap is not None:
            reasons.append(f"holdout_gap={float(h_gap):.4f}")
        if h_over == "high" or h_ok is False:
            reasons.append("holdout blocks promote")
            promote = False
            overfit = "high"
            worth_mc = True
            if next_action == "promote_paper_oms":
                next_action = "run_mc"
            confidence = max(confidence, 0.85)

        if std is not None and float(std) < 1e-12 and metrics.get("n_rows", 0) > 1:
            reasons.append("near-zero return std across combos — check data/signals")
            overfit = "high"
            promote = False
            next_action = "reject"
            confidence = 0.85

        return self._pack(next_action, promote, worth_mc, overfit, reasons, confidence)

    @staticmethod
    def _pack(
        next_action: str,
        promote: bool,
        worth_mc: bool,
        overfit: str,
        reasons: list[str],
        confidence: float,
    ) -> dict[str, Any]:
        return {
            "next_action": next_action,
            "promote_to_paper_oms": promote,
            "worth_mc_stress": worth_mc,
            "overfit_risk": overfit,
            "scores": {
                "promote": 1.0 if promote else 0.0,
                "mc": 1.0 if worth_mc else 0.0,
            },
            "reasons": reasons,
            "backend": "heuristic",
            "confidence": float(confidence),
        }


def triage_export(
    export_out: dict[str, Any],
    *,
    config: PolicyConfig | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build ResearchState + HeuristicPolicy decision in one call."""
    state = build_research_state(export_out, run_id=run_id)
    decision = HeuristicPolicy(config).decide(state)
    return {"state": state, "decision": decision}
