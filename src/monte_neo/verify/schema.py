"""``strategy-verdict/1`` schema, verdict aggregation and JSON helpers."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

VERDICT_SCHEMA_ID = "strategy-verdict/1"

VERDICTS = ("PASS", "PASS_WITH_WARNINGS", "NEEDS_MORE_EVIDENCE", "REJECT")
STATUSES = ("pass", "warn", "fail", "skip", "info")
CATEGORIES = ("integrity", "lookahead", "economics", "statistics")
# A fail in these categories means the backtest itself is not trustworthy.
HARD_CATEGORIES = ("integrity", "lookahead", "economics")

DISCLAIMER = (
    "Checks backtest methodology (look-ahead, costs, selection bias), not future profit. "
    "Not investment advice."
)

VERDICT_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://neozork.github.io/Monte-Neo/schema/strategy-verdict-1.json",
    "title": VERDICT_SCHEMA_ID,
    "type": "object",
    "required": ["schema", "verdict", "reasons", "checks", "metrics", "next_actions", "reproducibility"],
    "properties": {
        "schema": {"const": VERDICT_SCHEMA_ID},
        "verdict": {"enum": list(VERDICTS)},
        "certificate_id": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "category", "status", "summary"],
                "properties": {
                    "id": {"type": "string"},
                    "category": {"enum": list(CATEGORIES)},
                    "status": {"enum": list(STATUSES)},
                    "summary": {"type": "string"},
                    "details": {"type": "object"},
                },
            },
        },
        "metrics": {"type": "object"},
        "next_actions": {"type": "array", "items": {"type": "string"}},
        "reproducibility": {"type": "object"},
        "disclaimer": {"type": "string"},
        "signature": {
            "type": "object",
            "description": "Optional Ed25519 signature over the canonical JSON of the certificate without this field",
            "required": ["alg", "key_id", "public_key", "value"],
            "properties": {
                "alg": {"const": "ed25519"},
                "key_id": {"type": "string"},
                "public_key": {"type": "string"},
                "value": {"type": "string"},
            },
        },
    },
}


def aggregate_verdict(checks: list[dict[str, Any]]) -> str:
    """Map check statuses to one verdict (hard fail > stats fail > warn > pass)."""
    fails = [c for c in checks if c["status"] == "fail"]
    if any(c["category"] in HARD_CATEGORIES for c in fails):
        return "REJECT"
    if fails:
        return "NEEDS_MORE_EVIDENCE"
    if any(c["status"] == "warn" for c in checks):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def to_jsonable(obj: Any) -> Any:
    """Recursively convert numpy / non-finite values into strict-JSON types."""
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [to_jsonable(v) for v in obj.tolist()]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, float | np.floating):
        val = float(obj)
        return val if math.isfinite(val) else None
    return obj


__all__ = [
    "CATEGORIES",
    "DISCLAIMER",
    "HARD_CATEGORIES",
    "STATUSES",
    "VERDICTS",
    "VERDICT_JSON_SCHEMA",
    "VERDICT_SCHEMA_ID",
    "aggregate_verdict",
    "to_jsonable",
]
