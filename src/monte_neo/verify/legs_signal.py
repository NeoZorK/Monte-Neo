"""Signal-level checks for ``verify --legs``: does the timing of the leg positions carry the profit?

A legs table has the positions and prices but not the signal code, so the look-ahead probes and the information
coefficient cannot run. What can run is a permutation test on the positions themselves:

* ``legs_timing_significance``: the quantities of all legs are circularly shifted together against the prices (the
  hedge between the legs and the holding periods are kept, only the timing is destroyed). The net return the legs
  earned is compared with the shifted copies; ``p = (1 + #shifts at least as good) / (shifts + 1)``. A pairs strategy
  whose profit does not beat its own shifted copies earns from exposure or from drift, not from timing (the same
  idea as :mod:`monte_neo.verify.timing`, applied to the legs).
* ``legs_placebo``: each leg is shifted by its own random offset, so the hedge between them is broken and only the
  holdings' structure stays. A hedged spread earns because the legs are held *together*; if the placebo earns as much,
  the hedge relation adds nothing. Needs two or more legs.

Both warn only, with offsets drawn by a seeded generator (reproducible), starting at 5 % of the sample (at least 10 bars).
Rows for checks that need the strategy code are written as ``skip`` with the reason ("not assessed"):
``legs_lookahead`` and ``legs_signal_ic``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check

N_SHIFTS = 300
ALPHA = 0.05
SEED = 20261109
MIN_BARS = 60


def _arrays(body: pd.DataFrame, pnl: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(price changes, quantities over each bar, per-bar cost) as (bars-1, legs) / (bars-1,) arrays."""
    legs = [c[3:] for c in body.columns if c.startswith("px_")]
    px = np.column_stack([body[f"px_{leg}"].to_numpy(dtype=np.float64) for leg in legs])
    change = np.diff(np.log(px), axis=0) if pnl == "log" else px[1:] / px[:-1] - 1.0
    q = np.column_stack([body[f"qty_{leg}"].to_numpy(dtype=np.float64) for leg in legs])[1:]
    cost = body["cost"].to_numpy(dtype=np.float64)[1:] if "cost" in body.columns else np.zeros(change.shape[0])
    return change, q, cost


def _p_value(actual: float, null: np.ndarray) -> float:
    return float((1 + np.count_nonzero(null >= actual)) / (null.size + 1))


def legs_signal_rows(body: pd.DataFrame, *, pnl: str = "log", n_shifts: int = N_SHIFTS, seed: int = SEED) -> list[dict[str, Any]]:
    """The four signal-level rows for a legs table; see the module docstring."""
    change, q, cost = _arrays(body, pnl)
    n = change.shape[0]
    not_assessed = [
        check("legs_lookahead", "lookahead", "skip", "not assessed: a legs table has no signal code to re-run on truncated data; run verify --strategy with the OHLCV"),
        check("legs_signal_ic", "statistics", "skip", "not assessed: the information coefficient needs the signal values, not the held quantities"),
    ]
    lo = max(10, n // 20)
    if n < MIN_BARS or n - lo <= lo or not np.any(q):
        why = "too few bars" if n < MIN_BARS else "the legs never held a position"
        return [check("legs_timing_significance", "statistics", "skip", f"not assessed: {why}"),
                check("legs_placebo", "statistics", "skip", f"not assessed: {why}"), *not_assessed]
    actual = float((q * change).sum() - cost.sum())
    rng = np.random.default_rng(seed)
    offsets = rng.integers(lo, n - lo, size=n_shifts)
    timing = np.array([float((np.roll(q, int(k), axis=0) * change).sum() - np.roll(cost, int(k)).sum()) for k in offsets])
    p_t = _p_value(actual, timing)
    det_t = {"actual_return": actual, "p_value": p_t, "shifts": int(n_shifts), "shifted_median": float(np.median(timing))}
    if actual <= 0.0:
        t_row = check("legs_timing_significance", "statistics", "skip", "the legs do not earn a positive net return", det_t)
    elif p_t <= ALPHA:
        t_row = check("legs_timing_significance", "statistics", "pass", f"the legs beat {1 - p_t:.0%} of their own time-shifted copies (p={p_t:.3f})", det_t)
    else:
        t_row = check("legs_timing_significance", "statistics", "warn",
                      f"the legs' profit is not distinguishable from shifted copies of the same positions (p={p_t:.3f}): it comes from exposure, not timing", det_t)
    if change.shape[1] < 2:
        p_row = check("legs_placebo", "statistics", "skip", "not assessed: the placebo breaks the hedge between legs and needs two or more legs")
    else:
        placebo = np.empty(n_shifts)
        for i in range(n_shifts):
            shifted = np.column_stack([np.roll(q[:, j], int(rng.integers(lo, n - lo))) for j in range(q.shape[1])])
            placebo[i] = float((shifted * change).sum() - cost.sum())
        p_p = _p_value(actual, placebo)
        det_p = {"actual_return": actual, "p_value": p_p, "placebo_median": float(np.median(placebo)), "shifts": int(n_shifts)}
        if actual <= 0.0:
            p_row = check("legs_placebo", "statistics", "skip", "the legs do not earn a positive net return", det_p)
        elif p_p <= ALPHA:
            p_row = check("legs_placebo", "statistics", "pass", f"the held legs beat independently shifted legs (p={p_p:.3f}): the hedge relation adds return", det_p)
        else:
            p_row = check("legs_placebo", "statistics", "warn",
                          f"independently shifted legs earn as much (p={p_p:.3f}): the hedge relation between the legs adds nothing", det_p)
    return [t_row, p_row, *not_assessed]


NEXT_ACTIONS: dict[str, str] = {
    "legs_timing_significance": "The profit survives shifting the positions in time: it comes from holding the legs (drift, exposure), not from entering at the right moments. Neutralise the exposure or show the entries beat random entry.",
    "legs_placebo": "The legs earn about the same when each is held at an unrelated time: the pair relation is not what pays. Test the spread's mean reversion (verify --pairs-checks) before trusting the hedge.",
}

__all__ = ["ALPHA", "N_SHIFTS", "NEXT_ACTIONS", "legs_signal_rows"]
