"""Build compact ResearchState from an export_sma_sweep / export_batch dict."""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np

RESEARCH_STATE_SCHEMA = "mn.research_state.v1"


def build_research_state(export_out: dict[str, Any], *, run_id: str | None = None) -> dict[str, Any]:
    """Compress an export payload into a privacy-friendly research state.

    Does **not** include raw OHLCV — only metrics / checklist / timing.
    """
    metrics = dict(export_out.get("metrics") or {})
    rows = list(metrics.get("rows") or [])
    returns = np.asarray([float(r.get("total_return", 0.0)) for r in rows], dtype=float)
    if returns.size:
        summary = {
            "best_return": float(np.max(returns)),
            "worst_return": float(np.min(returns)),
            "mean_return": float(np.mean(returns)),
            "p50_return": float(np.median(returns)),
            "p95_return": float(np.percentile(returns, 95)),
            "std_return": float(np.std(returns)),
            "frac_positive": float(np.mean(returns > 0.0)),
            "n_rows": int(returns.size),
        }
        summary["edge_best_minus_p50"] = summary["best_return"] - summary["p50_return"]
    else:
        br = metrics.get("best_return")
        summary = {
            "best_return": float(br) if br is not None else None,
            "worst_return": None,
            "mean_return": None,
            "p50_return": None,
            "p95_return": None,
            "std_return": None,
            "frac_positive": None,
            "n_rows": 0,
            "edge_best_minus_p50": None,
        }

    top_rows = sorted(rows, key=lambda r: float(r.get("total_return", 0.0)), reverse=True)[:16]
    model = dict(export_out.get("model") or {})
    return {
        "schema": RESEARCH_STATE_SCHEMA,
        "run_id": run_id or str(uuid.uuid4()),
        "ok": bool(export_out.get("ok", True)),
        "device": export_out.get("device"),
        "fallback_reason": export_out.get("fallback_reason"),
        "bars": export_out.get("bars"),
        "combos": export_out.get("combos"),
        "export_api_version": export_out.get("export_api_version"),
        "engine": export_out.get("engine"),
        "lane": export_out.get("lane"),
        "model": model,
        "checklist": dict(export_out.get("work_checklist") or {}),
        "timing": dict(export_out.get("timing") or {}),
        "memory": dict(export_out.get("memory") or {}) or None,
        "metrics": summary,
        "top_rows": top_rows,
    }
