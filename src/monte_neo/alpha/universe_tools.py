"""Inputs that keep a cross-sectional test honest about who could be traded and held.

* ``liquid_mask`` / ``membership_from_mask``: a point-in-time liquid universe (top K by trailing traded value known *before* each
  date) instead of a static symbol list, with the membership windows derived from it.
* ``apply_terminal_returns``: a symbol whose data ends before the last date (delisted) gets a declared terminal return instead of
  keeping its last price for ever (zero P&L), the row ``delisting_returns`` lists what was declared and what was not.
* ``apply_rebalance_phase``: the portfolio is rebalanced on bar ``phase`` of every ``every`` bars and the scores are held in
  between, so the whole alpha path (IC, placebo, attribution, capacity) can be run for one phase.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.alpha.panel import Panel
from monte_neo.verify.checks import check


def liquid_mask(panel: Panel, top_k: int, lookback: int = 30) -> np.ndarray:
    """``(dates, symbols)`` bool: the ``top_k`` symbols by mean traded value over the ``lookback`` bars *before* each date.

    Raises:
        ValueError: ``top_k`` below 1, ``lookback`` below 2, or a panel without volume.
    """
    if top_k < 1 or lookback < 2:
        raise ValueError("top_k must be >= 1 and lookback >= 2")
    if panel.volume is None or not np.any(np.isfinite(panel.volume) & (panel.volume > 0)):
        raise ValueError("a liquid universe needs volume in the prices table")
    value = np.nan_to_num(panel.close * panel.volume, nan=0.0)
    trailing = pd.DataFrame(value).rolling(lookback, min_periods=lookback).mean().shift(1).to_numpy()  # strictly past bars
    mask = np.zeros_like(trailing, dtype=bool)
    for t in range(trailing.shape[0]):
        row = trailing[t]
        ok = np.flatnonzero(np.isfinite(row) & (row > 0))
        if ok.size:
            mask[t, ok[np.argsort(-row[ok], kind="stable")[:top_k]]] = True
    return mask


def membership_from_mask(panel: Panel, mask: np.ndarray) -> pd.DataFrame:
    """Membership windows ``symbol, start, end`` (end exclusive date of the first bar outside) from a bool mask."""
    rows = []
    dates = panel.dates
    for j, sym in enumerate(panel.symbols):
        col = np.concatenate([[False], mask[:, j], [False]])
        edges = np.flatnonzero(np.diff(col.astype(int)))
        for a, b in zip(edges[::2], edges[1::2], strict=True):
            rows.append({"symbol": sym, "start": dates[a], "end": dates[b - 1]})
    return pd.DataFrame(rows, columns=["symbol", "start", "end"])


def apply_terminal_returns(panel: Panel, terminal: dict[str, float] | None) -> tuple[Panel, dict[str, Any]]:
    """Give each delisted symbol its declared terminal return on the bar after its last price.

    A symbol is delisted when its last valid close is before the last date. ``terminal`` maps symbol to the return (``-1.0`` is a
    total loss). Returns the new panel and the check row ``delisting_returns``.
    """
    terminal = dict(terminal or {})
    unknown = sorted(set(terminal) - set(panel.symbols))
    if unknown:
        raise ValueError(f"terminal returns for symbols that are not in the prices: {', '.join(unknown[:5])}")
    if any(not np.isfinite(r) or r < -1.0 for r in terminal.values()):
        raise ValueError("a terminal return must be finite and at least -1.0 (a total loss)")
    close = panel.close.copy()
    ended, declared = [], []
    for j, sym in enumerate(panel.symbols):
        valid = np.flatnonzero(np.isfinite(close[:, j]))
        if valid.size == 0 or valid[-1] >= close.shape[0] - 1:
            continue
        ended.append(sym)
        if sym in terminal:
            close[valid[-1] + 1, j] = close[valid[-1], j] * (1.0 + terminal[sym])
            declared.append(sym)
    missing = [s for s in ended if s not in declared]
    details = {"ended": ended, "declared": declared, "undeclared": missing}
    if not ended:
        row = check("delisting_returns", "data", "skip", "no symbol's data ends before the last date", details)
    elif missing:
        row = check("delisting_returns", "data", "warn",
                    f"{len(missing)} of {len(ended)} symbols end early without a declared terminal return: their last price is kept, which prices a delisting at zero", details)
    else:
        row = check("delisting_returns", "data", "pass", f"all {len(ended)} symbols that end early have a declared terminal return", details)
    return replace(panel, close=close), row


def parse_phase(spec: str | tuple[int, int]) -> tuple[int, int]:
    """``"K/H"`` or ``(K, H)`` with ``0 <= K < H``."""
    k, h = (int(x) for x in (spec.split("/") if isinstance(spec, str) else spec))
    if h < 1 or not 0 <= k < h:
        raise ValueError("rebalance phase must be K/H with 0 <= K < H")
    return k, h


def apply_rebalance_phase(panel: Panel, spec: str | tuple[int, int]) -> Panel:
    """Scores seen only on bars ``K, K+H, K+2H, ...``; every other bar holds the last seen score."""
    k, h = parse_phase(spec)
    idx = np.arange(len(panel.dates))
    seen = pd.DataFrame(np.where((idx % h == k)[:, None], panel.scores, np.nan)).ffill().to_numpy()
    return replace(panel, scores=seen)


def prepare_panel(panel: Panel, *, liquid_top: int | None, liquid_lookback: int, terminal_returns: dict[str, float] | None,
                  rebalance_phase: str | None) -> tuple[Panel, list[dict[str, Any]], pd.DataFrame | None]:
    """Apply the optional inputs in a fixed order (delisting, liquid universe, rebalance phase); returns the panel, extra check rows, derived membership."""
    rows: list[dict[str, Any]] = []
    membership = None
    if terminal_returns is not None:
        panel, row = apply_terminal_returns(panel, terminal_returns)
        rows.append(row)
    if liquid_top:
        mask = liquid_mask(panel, liquid_top, liquid_lookback)
        panel = replace(panel, scores=np.where(mask, panel.scores, np.nan))
        membership = membership_from_mask(panel, mask)
    if rebalance_phase:
        panel = apply_rebalance_phase(panel, rebalance_phase)
    return panel, rows, membership


__all__ = ["prepare_panel", "apply_rebalance_phase", "apply_terminal_returns", "liquid_mask", "membership_from_mask", "parse_phase"]
