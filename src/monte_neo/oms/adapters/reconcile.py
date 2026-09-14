"""Blotter vs venue report reconciliation helpers."""

from __future__ import annotations

from typing import Any

from monte_neo.oms.adapters.base import FillReport


def reconcile_fills(
    local: list[dict[str, Any]],
    venue: list[FillReport],
    *,
    qty_tol: float = 1e-9,
    px_tol: float = 1e-9,
) -> dict[str, Any]:
    """Compare local fill dicts to venue FillReports (order-insensitive by qty sum)."""
    local_qty = sum(float(f.get("qty", 0.0)) for f in local)
    venue_qty = sum(f.qty for f in venue)
    local_notional = sum(float(f.get("qty", 0.0)) * float(f.get("price", 0.0)) for f in local)
    venue_notional = sum(f.qty * f.price for f in venue)
    ok = abs(local_qty - venue_qty) <= qty_tol and (
        abs(local_notional - venue_notional) <= px_tol * max(1.0, venue_qty)
    )
    return {
        "ok": ok,
        "local_qty": local_qty,
        "venue_qty": venue_qty,
        "local_notional": local_notional,
        "venue_notional": venue_notional,
        "n_local": len(local),
        "n_venue": len(venue),
    }
