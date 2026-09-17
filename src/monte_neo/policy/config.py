"""Tunable thresholds for HeuristicPolicy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PolicyConfig:
    """Deterministic triage thresholds (no ML)."""

    t_min_return: float = 0.0
    t_promote_return: float = 0.05
    p_min_frac_positive: float = 0.15
    e_hi_edge: float = 0.15
    top_k: int = 5
    cluster_fast_tol: int = 2
    cluster_slow_tol: int = 5
    confidence_floor: float = 0.55

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
