"""Suggest a profile from the input. A hint, never imposed: the caller decides."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np

from monte_neo.profiles.registry import get_profile


def _score(columns: set[str], positions: np.ndarray | None) -> dict[str, tuple[int, str]]:
    found: dict[str, tuple[int, str]] = {}

    def add(pid: str, score: int, why: str) -> None:
        if pid not in found or found[pid][0] < score:
            found[pid] = (score, why)

    low = {c.lower() for c in columns}
    if {"strike", "expiry"} <= low or {"strike", "expiration"} <= low:
        add("options", 9, "the table has strike and expiry columns")
    if low & {"funding_rate", "funding_bps"} and low & {"perp_close", "spot_close"}:
        add("carry", 9, "funding and spot/perp price columns")
    if any(c.startswith("px_") for c in low) and any(c.startswith("qty_") for c in low):
        add("pairs_stat_arb", 9, "leg price and quantity columns")
    if any(c.startswith("ev_") for c in low) or "published_at" in low:
        add("event_driven", 7, "event columns joined by publication time")
    if "symbol" in low:
        add("cross_sectional", 5, "several symbols in one table")
    if low & {"iv", "vix", "implied_vol"}:
        add("short_volatility", 4, "implied-volatility column")
    if positions is not None and positions.size:
        pos = np.asarray(positions, dtype=float)
        if pos.ndim == 2:
            net = np.nanmean(np.nansum(pos, axis=1))
            add("cross_sectional", 5, "a matrix of positions across instruments")
            if np.isfinite(net) and abs(net) < 0.1 and (pos < 0).any():
                add("market_neutral", 6, "long and short books that net to about zero")
            add("allocation_risk_parity", 3, "weights across instruments")
        else:
            flat = np.nanmean(pos == 0)
            if np.nanmin(pos) >= 0 and np.nanmean(pos > 0) > 0.98:
                add("buy_and_hold", 8, "always long, almost never flat")
            elif (pos < 0).any() and (pos > 0).any():
                add("trend_cta", 3, "long and short on one instrument")
            elif flat > 0.5:
                add("mean_reversion", 3, "flat most of the time, short episodes")
    return found


def suggest_profiles(columns: Iterable[str] = (), positions: Any = None, *, top: int = 3) -> list[dict[str, Any]]:
    """Up to ``top`` suggestions, best first, each with ``id``, ``title``, ``score`` and ``why``; possibly empty.

    Options is suggested by the column names only (strike and expiry).
    """
    arr = None if positions is None else np.asarray(positions)
    out = []
    for pid, (score, why) in sorted(_score(set(columns), arr).items(), key=lambda kv: -kv[1][0]):
        out.append({"id": pid, "title": get_profile(pid)["title"], "score": score, "why": why})
    return out[:top]
