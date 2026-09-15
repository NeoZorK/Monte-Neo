"""Trade journal helpers for the professional bar engine."""

from __future__ import annotations

from typing import Any

import numpy as np

# Reason codes written by the Numba core (keep in sync with bar_engine).
REASON_SIGNAL = 1
REASON_SL = 2
REASON_TP = 3
REASON_FLATTEN = 4
REASON_TRAIL = 5

REASON_NAMES = {
    REASON_SIGNAL: "signal",
    REASON_SL: "sl",
    REASON_TP: "tp",
    REASON_FLATTEN: "flatten",
    REASON_TRAIL: "trail",
}


def pack_trades(
    n_closed: int,
    entry_idx: np.ndarray,
    exit_idx: np.ndarray,
    entry_px: np.ndarray,
    exit_px: np.ndarray,
    qty: np.ndarray,
    fees: np.ndarray,
    reason: np.ndarray,
) -> list[dict[str, Any]]:
    """Convert fixed-size Numba trade buffers into a Python trade list."""
    rows: list[dict[str, Any]] = []
    for i in range(int(n_closed)):
        q = float(qty[i])
        ep = float(entry_px[i])
        xp = float(exit_px[i])
        pnl = q * (xp - ep) - float(fees[i])
        code = int(reason[i])
        rows.append(
            {
                "entry_idx": int(entry_idx[i]),
                "exit_idx": int(exit_idx[i]),
                "entry_px": ep,
                "exit_px": xp,
                "qty": q,
                "fees": float(fees[i]),
                "pnl": pnl,
                "reason": REASON_NAMES.get(code, f"code_{code}"),
                "reason_code": code,
            }
        )
    return rows


def trade_stats(trades: list[dict[str, Any]]) -> dict[str, float]:
    """Win rate and profit factor from closed trades."""
    if not trades:
        return {"win_rate": 0.0, "profit_factor": 0.0, "n_closed_trades": 0.0}  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    pnls = np.array([t["pnl"] for t in trades], dtype=np.float64)
    wins = pnls[pnls > 0.0]
    losses = pnls[pnls < 0.0]
    gross_win = float(np.sum(wins)) if wins.size else 0.0
    gross_loss = float(-np.sum(losses)) if losses.size else 0.0
    if gross_loss > 0.0:
        pf = gross_win / gross_loss
    else:
        pf = float("inf") if gross_win > 0.0 else 0.0
    return {
        "win_rate": float(np.mean(pnls > 0.0)),
        "profit_factor": float(pf) if np.isfinite(pf) else 1e6,
        "n_closed_trades": float(len(trades)),
    }
