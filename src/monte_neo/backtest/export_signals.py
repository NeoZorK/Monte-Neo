"""Bring-your-own-signals export: any strategy's positions through the research bar.

Positions are reduced to their sign (``+1`` long, ``0`` flat, ``-1`` short);
NaN means flat. The export records a SHA-256 of the normalized positions so a
verdict or harness can prove which signal array was evaluated.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from monte_neo.backtest.export import export_single
from monte_neo.backtest.model import ExecutionModel


def normalize_positions(signals: Any) -> np.ndarray:
    """Return int64 positions in ``{-1, 0, 1}`` from any numeric array-like."""
    arr = np.asarray(signals, dtype=np.float64).reshape(-1)
    return np.sign(np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=-1.0)).astype(np.int64)


def export_signals(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signals: Any,
    model: ExecutionModel | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run caller-supplied positions through :func:`export_single`.

    Extra keyword arguments (``include_equity``, ``include_journal``, ...)
    are forwarded unchanged.
    """
    pos = normalize_positions(signals)
    if pos.shape[0] != np.asarray(close).shape[0]:
        raise ValueError(f"signal length {pos.shape[0]} != bar count {np.asarray(close).shape[0]}")
    out = export_single(open_, high, low, close, pos, model=model, **kwargs)
    out["engine"] = "monte_neo.backtest.export_signals"
    out["signal"] = {
        "sha256": hashlib.sha256(np.ascontiguousarray(pos).tobytes()).hexdigest(),
        "exposure": float(np.mean(pos != 0)) if pos.size else 0.0,
        "position_changes": int(np.count_nonzero(np.diff(pos))) if pos.size > 1 else 0,
        "has_short": bool(np.any(pos < 0)),
    }
    return out


__all__ = ["export_signals", "normalize_positions"]
