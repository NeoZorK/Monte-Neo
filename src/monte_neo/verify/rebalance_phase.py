"""Does the result depend on the day (phase) the portfolio is rebalanced?

A strategy that rebalances every ``k`` bars is one of ``k`` equally valid versions: the same decisions, taken on a
different weekday. If one phase earns and another loses, the result is the luck of the calendar. The test delays the
positions by ``p = 0..k-1`` bars (for a signal that changes only on rebalance bars this is exactly a shift of the
rebalance phase), re-runs the backtest with the same costs, and reports the **worst phase as the headline** next to the
mean and the spread. Averaging over phases (staggered tranches) is the standard remedy (see the repair catalogue, R7).

The cadence ``k`` is the dominant gap between bars where the positions change (taken when at least half of the gaps are
equal); pass ``rebalance_every`` to set it. Strategies that trade at irregular times, or every bar, are skipped.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.checks import check
from monte_neo.verify.costs import delay_signals
from monte_neo.verify.engine import total_return as _total_return

MAX_PHASES = 12
SPREAD_WARN = 0.5  # (best - worst) over |mean| above this is a calendar effect
MIN_CHANGES = 6


def detect_cadence(signals: np.ndarray) -> int | None:
    """The rebalance interval in bars, or ``None`` when positions change every bar, too rarely, or irregularly."""
    s = np.asarray(signals, dtype=np.float64)
    s = s.reshape(s.shape[0], -1)
    changed = np.flatnonzero(np.any(np.abs(np.diff(s, axis=0)) > 1e-12, axis=1)) + 1
    if changed.size < MIN_CHANGES:
        return None
    gaps = np.diff(changed)
    k = int(np.bincount(gaps).argmax())
    if k < 2 or float(np.mean(gaps == k)) < 0.5:
        return None
    return k


def rebalance_phase_row(
    ohlc: dict[str, np.ndarray], signals: np.ndarray, model: ExecutionModel, rebalance_every: int | None = None
) -> dict[str, Any]:
    """Row ``rebalance_timing_luck`` from delays ``0..k-1`` of the positions.

    ``warn`` when the worst phase loses money while phase 0 does not, or when the best-worst spread exceeds half of the
    mean absolute return; ``skip`` when no cadence is found or phase 0 is not profitable.

    Raises:
        ValueError: ``rebalance_every`` below 2.
    """
    if rebalance_every is not None and int(rebalance_every) < 2:
        raise ValueError("rebalance_every must be >= 2 bars")
    k = int(rebalance_every) if rebalance_every else detect_cadence(signals)
    if k is None:
        return check("rebalance_timing_luck", "statistics", "skip", "no regular rebalance cadence found (pass rebalance_every to set it)")
    phases = sorted({int(round(x)) for x in np.linspace(0, k - 1, min(k, MAX_PHASES))})
    rets = {p: float(_total_return(ohlc, delay_signals(signals, p), model)) for p in phases}
    vals = np.array(list(rets.values()))
    worst, best, mean = float(vals.min()), float(vals.max()), float(vals.mean())
    det = {"k": k, "phases": {str(p): r for p, r in rets.items()}, "worst_return": worst, "best_return": best,
           "mean_return": mean, "std_return": float(vals.std()), "primary_return": worst}
    if rets[0] <= 0.0:
        return check("rebalance_timing_luck", "statistics", "skip", "not profitable at the original rebalance phase", det)
    spread = (best - worst) / max(abs(mean), 1e-12)
    text = f"{len(phases)} rebalance phases of {k} bars: worst {worst:+.1%}, mean {mean:+.1%}, best {best:+.1%}"
    if worst <= 0.0:
        return check("rebalance_timing_luck", "statistics", "warn", "the result is the luck of the rebalance day: " + text, det)
    if spread > SPREAD_WARN:
        return check("rebalance_timing_luck", "statistics", "warn", f"the result depends on the rebalance day (spread {spread:.0%} of the mean): " + text, det)
    return check("rebalance_timing_luck", "statistics", "pass", text, det)


__all__ = ["MAX_PHASES", "SPREAD_WARN", "detect_cadence", "rebalance_phase_row"]
