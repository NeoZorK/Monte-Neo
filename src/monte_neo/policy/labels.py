"""Append-only JSONL log for research decisions (seed corpus for a future LocalScorer).

Not a model. Offline file append only.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LABEL_SCHEMA = "mn.research_label.v1"


def append_research_label(
    path: str | Path,
    *,
    holdout_report: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    human_label: str | None = None,
    notes: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one label record. ``human_label`` e.g. accept / reject / mc / skip."""
    rec: dict[str, Any] = {
        "schema": LABEL_SCHEMA,
        "ts_utc": datetime.now(UTC).isoformat(),
        "human_label": human_label,
        "notes": notes,
    }
    if holdout_report is not None:
        m = dict(holdout_report.get("metrics") or {})
        tr = dict(holdout_report.get("train") or {})
        ho = dict(holdout_report.get("holdout") or {})
        rec["holdout"] = {
            "promote_ok": m.get("promote_ok"),
            "next_action": m.get("next_action"),
            "overfit_risk": m.get("overfit_risk"),
            "promote_mode": m.get("promote_mode"),
            "gap_best": m.get("gap_best"),
            "mean_gap_top_k": m.get("mean_gap_top_k"),
            "train_best": tr.get("best_return"),
            "holdout_at_best": ho.get("at_train_best"),
            "best_pair": tr.get("best_pair"),
            "split": holdout_report.get("split"),
        }
    if decision is not None:
        rec["decision"] = {
            "next_action": decision.get("next_action"),
            "promote_to_paper_oms": decision.get("promote_to_paper_oms"),
            "worth_mc_stress": decision.get("worth_mc_stress"),
            "overfit_risk": decision.get("overfit_risk"),
            "backend": decision.get("backend"),
            "confidence": decision.get("confidence"),
            "reasons": decision.get("reasons"),
        }
    if extra:
        rec["extra"] = extra

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


__all__ = ["LABEL_SCHEMA", "append_research_label"]
