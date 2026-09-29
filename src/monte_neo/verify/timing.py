"""Timing significance: does the signal beat shifted copies of itself?

A strategy can be profitable only because it holds the market while prices drift up.
Circularly shifting the positions against the prices keeps the exposure, the trade
count and the holding periods, and destroys only the timing. If the real return does
not beat most shifted copies, the profit comes from market exposure, not from the signal.

Offsets are evenly spaced (no randomness), so the result is reproducible and belongs
in a certificate.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.backtest.core_numba import run_terminal_return
from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.engine import is_weights
from monte_neo.verify.engine import total_return as _weights_return

N_SHIFTS = 200
ALPHA = 0.05


def _terminal_return(ohlc: dict[str, np.ndarray], signals: np.ndarray, model: ExecutionModel) -> float:
    if is_weights(signals):
        return _weights_return(ohlc, signals, model)
    n = signals.size
    return float(
        run_terminal_return(
            ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], signals, np.ones(n, dtype=np.bool_),
            model.fill_policy == "next_bar_open", model.side_mode == "long_short", float(model.size_fraction),
            float(model.commission_bps), float(model.effective_slip_bps), float(model.initial_cash),
            int(model.warmup_bars), float(model.sl_pct), float(model.tp_pct), float(model.trail_pct),
            float(model.fill_fraction), float(model.leverage), float(model.funding_bps_per_bar),
        )
    )


def timing_significance(
    ohlc: dict[str, np.ndarray],
    signals: np.ndarray,
    model: ExecutionModel,
    *,
    n_shifts: int = N_SHIFTS,
    alpha: float = ALPHA,
) -> dict[str, Any]:
    """p-value of the net return against ``n_shifts`` circular shifts of the positions.

    ``p = (1 + #shifts with return >= actual) / (n_shifts + 1)``. Shifts start at 5% of
    the sample (at least 10 bars) so a shifted copy never overlaps its own timing.
    """
    sig = np.asarray(signals)
    sig = np.ascontiguousarray(sig if is_weights(sig) else sig.astype(np.int64))
    n = sig.shape[0]
    ohlc = {k: np.ascontiguousarray(v, dtype=np.float64) for k, v in ohlc.items()}
    actual = _terminal_return(ohlc, sig, model)
    lo = max(10, n // 20)
    hi = n - lo
    if hi <= lo or not np.any(sig):
        return {"status": "skip", "p_value": None, "actual_return": actual, "n_shifts": 0}
    offsets = np.unique(np.linspace(lo, hi, num=int(n_shifts)).astype(np.int64))
    # Shift along time only: a multi-instrument matrix keeps its cross-section together.
    shifted = np.array([_terminal_return(ohlc, np.roll(sig, int(k), axis=0), model) for k in offsets])
    shifted = shifted[np.isfinite(shifted)]  # defensive: a copy without a finite result is not evidence
    if shifted.size == 0:
        return {"status": "skip", "p_value": None, "actual_return": actual, "n_shifts": 0}
    beaten = int(np.count_nonzero(shifted < actual))
    p_value = float((1 + np.count_nonzero(shifted >= actual)) / (shifted.size + 1))
    return {
        "status": "pass" if p_value <= alpha else "warn",
        "p_value": p_value,
        "alpha": float(alpha),
        "actual_return": actual,
        "n_shifts": int(shifted.size),
        "share_beaten": beaten / shifted.size,
        "shifted_median_return": float(np.median(shifted)),
    }


__all__ = ["timing_significance"]
