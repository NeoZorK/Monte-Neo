"""Corporate actions: declared splits and dividends against the price series.

The declared actions are a table of ``bar`` (index of the first bar on which the action is in the price; or a ``date``
matched to the timestamps), ``kind`` (``split`` or ``dividend``) and ``value`` (split ratio, new shares per old: 2 for
a 2-for-1 and 0.5 for a 1-for-2; or the cash dividend per share in price units).

Checks (row ``corporate_actions``):

* **Split declared but still in the prices**: an unadjusted series shows a jump of about ``1 / ratio`` from the previous
  close into the action bar. A strategy reads it as a crash or a boom, so the profit it makes there is fake. ``fail``
  (it is a data error that creates profit), the same rule as an unadjusted split in the quality check.
* **Split-like jump with no declared action** (the jumps found by
  :func:`monte_neo.verify.quality.split_jumps`): ``warn``, the action list is incomplete or the vendor adjusted wrongly.
* **Dividends**: a price-only series leaves the dividend out of the return. The income a long position would have
  received (a short pays it) is estimated as ``position[t-1] * dividend / close[t-1]`` summed over the ex-bars, and the
  row warns when it is at least 10 % of the net return or 1 % of capital in absolute terms. :func:`total_return_adjust`
  returns prices adjusted backwards for dividends (and splits) so a re-run can include them (the proportional
  back-adjustment used by CRSP-style total-return series; Fama and French 1992 compute returns with dividends).
* **Inconsistent action**: a dividend of at least the previous close, a non-positive ratio, a repeated bar or a bar
  outside the series is refused with a ``ValueError`` that names the row.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check
from monte_neo.verify.quality import split_jumps

SPLIT_MATCH = 0.12  # relative tolerance of an observed jump against 1 / ratio
INCOME_SHARE_WARN = 0.10
INCOME_ABS_WARN = 0.01
KINDS = ("split", "dividend")


def parse_actions(actions: Any, n_bars: int, timestamps: Any = None) -> list[tuple[int, str, float]]:
    """Validate a declared action table; returns ``[(bar, kind, value)]`` sorted by bar.

    Raises:
        ValueError: A missing column, a unknown kind, a non-positive value, a bar outside ``1..n_bars-1`` or two split / two
            dividend rows on the same bar.
    """
    df = pd.DataFrame(actions)
    if df.empty:
        return []
    if not {"kind", "value"} <= set(df.columns) or not ({"bar", "date"} & set(df.columns)):
        raise ValueError("corporate actions need columns kind, value and bar (or date)")
    out: list[tuple[int, str, float]] = []
    seen: set[tuple[int, str]] = set()
    ts = pd.to_datetime(pd.Series(timestamps), utc=True) if timestamps is not None else None
    for i, row in df.iterrows():
        kind, value = str(row["kind"]), float(row["value"])
        if kind not in KINDS:
            raise ValueError(f"row {i}: kind must be one of {KINDS}, got {kind!r}")
        if not np.isfinite(value) or value <= 0.0:
            raise ValueError(f"row {i}: value must be positive")
        if "bar" in df.columns and pd.notna(row.get("bar")):
            bar = int(row["bar"])
        else:
            if ts is None:
                raise ValueError(f"row {i}: a date needs timestamps in the data")
            hit = np.flatnonzero((ts >= pd.to_datetime(row["date"], utc=True)).to_numpy())
            if hit.size == 0:
                raise ValueError(f"row {i}: the date is after the last bar")
            bar = int(hit[0])
        if not 1 <= bar < n_bars:
            raise ValueError(f"row {i}: bar {bar} is outside the series")
        if (bar, kind) in seen:
            raise ValueError(f"row {i}: two {kind} actions on bar {bar}")
        seen.add((bar, kind))
        out.append((bar, kind, value))
    return sorted(out)


def total_return_adjust(ohlc: dict[str, np.ndarray], actions: list[tuple[int, str, float]], *, splits: bool = False) -> dict[str, np.ndarray]:
    """Prices adjusted backwards for dividends (and, with ``splits=True``, for splits that are still in the prices).

    Every price before an action bar is multiplied by ``1 - dividend / close[bar-1]`` (dividend) or divided by the ratio
    (split). Raises ``ValueError`` when a dividend is not smaller than the previous close.
    """
    out = {k: np.array(v, dtype=np.float64) for k, v in ohlc.items()}
    close = np.asarray(ohlc["close"], dtype=np.float64)
    for bar, kind, value in sorted(actions, reverse=True):
        if kind == "dividend":
            if value >= close[bar - 1]:
                raise ValueError(f"dividend {value} is not below the previous close {close[bar - 1]} (bar {bar})")
            f = 1.0 - value / close[bar - 1]
        elif splits:
            f = 1.0 / value
        else:
            continue
        for k in out:
            out[k][:bar] *= f
    return out


def dividend_income(position: np.ndarray, close: np.ndarray, actions: list[tuple[int, str, float]]) -> float:
    """Return from dividends a position would have collected (a short pays): ``sum position[t-1] * D / close[t-1]``."""
    pos = np.asarray(position, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    total = 0.0
    for bar, kind, value in actions:
        if kind == "dividend":
            total += float(pos[bar - 1]) * value / float(c[bar - 1])
    return total


def corporate_actions_row(
    ohlc: dict[str, np.ndarray], actions: list[tuple[int, str, float]], position: np.ndarray, total_return: float,
) -> dict[str, Any]:
    """Row ``corporate_actions`` for one instrument; see the module docstring."""
    o, c = np.asarray(ohlc["open"], dtype=np.float64), np.asarray(ohlc["close"], dtype=np.float64)
    pending, declared = [], {bar for bar, kind, _ in actions if kind == "split"}
    for bar, kind, value in actions:
        if kind != "split":
            continue
        jump = max(o[bar] / c[bar - 1], c[bar] / c[bar - 1]) if value < 1.0 else min(o[bar] / c[bar - 1], c[bar] / c[bar - 1])
        expected = 1.0 / value
        if min(abs(o[bar] / c[bar - 1] / expected - 1.0), abs(c[bar] / c[bar - 1] / expected - 1.0)) <= SPLIT_MATCH:
            pending.append({"bar": int(bar), "ratio": float(value), "observed_jump": float(jump)})
    undeclared = [{"bar": int(t), "ratio": float(x)} for t, _, x in split_jumps(ohlc) if int(t) not in declared]
    income = dividend_income(position, c, actions)
    details = {"actions": len(actions), "unadjusted_splits": pending, "undeclared_jumps": undeclared, "dividend_income": income}
    if pending:
        first = pending[0]
        return check("corporate_actions", "data", "fail",
                     f"a declared split on bar {first['bar']} (ratio {first['ratio']:g}) is still in the prices as a jump of {first['observed_jump']:.2f}x: "
                     "the strategy trades a fake move; adjust the history", details)
    problems = []
    if undeclared:
        problems.append(f"{len(undeclared)} split-like price jump(s) have no declared action (first at bar {undeclared[0]['bar']})")
    material = (total_return > 0.0 and abs(income) >= INCOME_SHARE_WARN * total_return) or abs(income) >= INCOME_ABS_WARN
    if material:
        side = "collects" if income > 0 else "pays"
        problems.append(f"dividends are not in the price return: the positions {side} about {abs(income):.1%} in dividends over the test (use total_return_adjust)")
    if problems:
        return check("corporate_actions", "data", "warn", "; ".join(problems), details)
    return check("corporate_actions", "data", "pass", f"{len(actions)} declared action(s) are consistent with the prices; dividend effect {income:+.2%}", details)


__all__ = ["corporate_actions_row", "dividend_income", "parse_actions", "total_return_adjust"]
