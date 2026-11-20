"""Checks that need no OHLCV: data integrity of a return or leg-price series, and an honest ARL for it.

``verify --returns`` and ``verify --legs`` get a ``data_integrity`` row built from the series itself (finite values, ordered
unique dates, no gaps far beyond the usual spacing, no return of -100 % or worse, no frozen prices). It is the same row id
the OHLCV path uses, so the Alpha Readiness Level can credit level 1 ("idea on clean data").

Everything above level 1 needs evidence a bare series cannot give (look-ahead probes need the code or the positions, costs
need fills, timing needs exposure). Those levels stay "not assessed" and :func:`series_readiness` says so in plain words;
the cap is a statement about missing evidence, not a verdict on the strategy.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.readiness import readiness
from monte_neo.verify.checks import check

GAP_FACTOR = 5.0  # a gap this many times the median spacing is reported (a weekend in daily data is 3x)
FROZEN_RUN = 10  # this many identical consecutive non-zero values (or prices) look like a stale feed
JUMP = 0.5  # a one-bar price move of 50 % or more looks like an unadjusted split or a bad tick


def _longest_run(a: np.ndarray) -> int:
    if a.size == 0:
        return 0
    change = np.flatnonzero(np.diff(a) != 0)
    edges = np.concatenate([[-1], change, [a.size - 1]])
    return int(np.max(np.diff(edges)))


def series_integrity(
    index: pd.DatetimeIndex, returns: np.ndarray, prices: dict[str, np.ndarray] | None = None
) -> dict[str, Any]:
    """The ``data_integrity`` row of a return series (and, for legs, of the leg prices).

    Args:
        index: Dates, in the order given (a backward or repeated date is a failure).
        returns: Per-period decimal returns.
        prices: Optional ``{leg: price array}`` for legs files; checked for frozen runs and one-bar jumps.

    Returns:
        A check row: ``fail`` for non-finite values, repeated or backward dates, or a return <= -100 %;
        ``warn`` for date gaps, frozen non-zero returns or prices, and price jumps (data errors that fake profit);
        otherwise ``pass``.
    """
    r = np.asarray(returns, dtype=np.float64)
    n_nan = int(np.count_nonzero(~np.isfinite(r)))
    n_total_loss = int(np.count_nonzero(np.nan_to_num(r) <= -1.0))
    n_dup = int(index.duplicated().sum())
    n_back = int(np.count_nonzero(np.diff(index.asi8) < 0))
    steps = np.diff(index.asi8).astype(np.float64)
    pos = steps[steps > 0]
    gaps = int(np.count_nonzero(pos > GAP_FACTOR * np.median(pos))) if pos.size else 0
    frozen = _longest_run(r[r != 0.0]) if r.size else 0
    price_frozen = price_jumps = 0
    for px in (prices or {}).values():
        price_frozen = max(price_frozen, _longest_run(np.asarray(px, dtype=np.float64)))
        price_jumps += int(np.count_nonzero(np.abs(np.diff(np.log(px))) >= np.log1p(JUMP)))
    hard = [(n_nan, "non-finite value"), (n_dup, "duplicate date"), (n_back, "out-of-order date"), (n_total_loss, "return <= -100%")]
    soft = [(gaps, f"date gap over {GAP_FACTOR:.0f}x the usual spacing"),
            (1 if frozen >= FROZEN_RUN else 0, f"{frozen} identical non-zero returns in a row"),
            (1 if price_frozen >= FROZEN_RUN else 0, f"price frozen for {price_frozen} bars"),
            (price_jumps, f"price move of {JUMP:.0%} or more in one bar")]
    found_hard = [f"{c} {t}" if c > 1 else t for c, t in hard if c]
    found_soft = [f"{c} {t}" if c > 1 else t for c, t in soft if c]
    details = {"non_finite": n_nan, "duplicate_dates": n_dup, "out_of_order_dates": n_back, "total_loss_returns": n_total_loss,
               "date_gaps": gaps, "longest_frozen_return_run": frozen, "longest_frozen_price_run": price_frozen,
               "price_jumps": price_jumps}
    if found_hard:
        return check("data_integrity", "integrity", "fail", "series is broken: " + ", ".join(found_hard + found_soft), details)
    if found_soft:
        return check("data_integrity", "integrity", "warn", "series looks suspicious: " + ", ".join(found_soft), details)
    return check("data_integrity", "integrity", "pass", "series is clean: finite, ordered, unique dates, no gaps, no frozen values", details)


def series_readiness(report: dict[str, Any], kind: str) -> dict[str, Any]:
    """The Alpha Readiness Level of a returns or legs report, with a plain statement of why it stops where it does.

    Args:
        report: A ``verify_returns`` / ``verify_legs`` report (its checks include ``data_integrity``).
        kind: ``"returns"`` or ``"legs"``.

    Returns:
        The ``alpha-readiness/1`` dict plus ``scope``: what this input cannot show and which run assesses it.
    """
    out = readiness(certificate=report)
    out["scope"] = (
        f"ARL for a {kind} input is capped by the evidence a series can give: data cleanliness (level 1) is checked here; "
        "look-ahead, costs, timing and tradability need the strategy code or the position history and market data "
        "(run monte-neo verify --strategy with the OHLCV). Levels shown as 'not assessed' are missing evidence, not failures."
    )
    return out


__all__ = ["FROZEN_RUN", "GAP_FACTOR", "JUMP", "series_integrity", "series_readiness"]
