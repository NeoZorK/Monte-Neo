"""C4: is the new score a new signal, or the old signals again? Partial rank IC after removing the existing scores."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.alpha._core import ic_series, newey_west_t, rank_rows
from monte_neo.alpha.attribution_ols import nw_lag
from monte_neo.alpha.panel import TIME_ALIASES, Panel, _frame, _pick
from monte_neo.verify.checks import check
from monte_neo.verify.market import SYMBOL_ALIASES

MIN_DATES = 20
T_SIGNIFICANT = 2.0


def load_existing_scores(path: str | Path | pd.DataFrame, panel: Panel) -> dict[str, np.ndarray]:
    """Read a long table (timestamp, symbol, one column per existing signal) and align it to the panel.

    Args:
        path: A .csv / .parquet path or a DataFrame.
        panel: The panel whose dates and symbols the matrices follow.

    Returns:
        ``{signal name: (dates x symbols) matrix}``; missing cells are NaN.

    Raises:
        ValueError: no signal column, duplicate (timestamp, symbol) rows, or unparseable timestamps.
    """
    df = _frame(path)
    tcol, scol = _pick(df, TIME_ALIASES, "timestamp"), _pick(df, SYMBOL_ALIASES, "symbol")
    names = [c for c in df.columns if c not in (tcol, scol)]
    if not names:
        raise ValueError("the existing-scores table needs at least one signal column besides timestamp and symbol")
    ts = pd.to_datetime(df[tcol], errors="coerce", utc=True)
    if ts.isna().any():
        raise ValueError(f"{int(ts.isna().sum())} unparseable timestamps in column '{tcol}'")
    long = pd.DataFrame({"timestamp": ts.dt.tz_localize(None), "symbol": df[scol].astype(str).str.strip()})
    if long.duplicated().any():
        raise ValueError(f"{int(long.duplicated().sum())} duplicate (timestamp, symbol) rows in the existing-scores table")
    out: dict[str, np.ndarray] = {}
    for name in names:
        long[name] = pd.to_numeric(df[name], errors="coerce").to_numpy()
        wide = long.pivot(index="timestamp", columns="symbol", values=name)
        out[str(name)] = wide.reindex(index=panel.dates, columns=panel.symbols).to_numpy(float)
    return out


def _residualise(y: np.ndarray, xs: list[np.ndarray]) -> np.ndarray:
    """Per date, the residual of the candidate's ranks after an OLS on the ranks of the existing scores."""
    ok = np.isfinite(y)
    for x in xs:
        ok &= np.isfinite(x)
    ry = rank_rows(np.where(ok, y, np.nan))
    rx = [rank_rows(np.where(ok, x, np.nan)) for x in xs]
    out = np.full_like(y, np.nan, dtype=float)
    k = len(xs)
    for t in range(y.shape[0]):
        m = ok[t]
        if m.sum() < k + 3:
            continue
        a = np.column_stack([np.ones(int(m.sum()))] + [r[t, m] for r in rx])
        beta, *_ = np.linalg.lstsq(a, ry[t, m], rcond=None)
        out[t, m] = ry[t, m] - a @ beta
    return out


def signal_orthogonality(panel: Panel, existing: dict[str, np.ndarray] | pd.DataFrame, horizon: int = 1) -> dict[str, Any]:
    """Row ``signal_orthogonality`` (category ``statistics``): the partial rank IC of the candidate given the existing scores.

    Warns when the partial IC has |t| < 2 while the raw IC has t >= 2: the new score repeats signals you already have.

    Args:
        panel: Aligned prices and the candidate scores.
        existing: ``{name: dates x symbols matrix}`` or a long DataFrame (see :func:`load_existing_scores`).
        horizon: Forward-return horizon in bars.
    """
    if isinstance(existing, pd.DataFrame):
        existing = load_existing_scores(existing, panel)
    xs = [np.asarray(v, float) for v in existing.values()]
    if not xs:
        return check("signal_orthogonality", "statistics", "skip", "no existing scores given")
    if any(x.shape != panel.scores.shape for x in xs):
        raise ValueError(f"existing scores must have the panel shape {panel.scores.shape}")
    fwd = panel.forward_returns(horizon)
    base = np.where(np.all([np.isfinite(x) for x in xs], axis=0), panel.scores, np.nan)  # raw IC on the same cells
    raw = ic_series(base, fwd)
    part = ic_series(_residualise(panel.scores, xs), fwd)
    n = int(np.isfinite(part).sum())
    if n < MIN_DATES:
        return check("signal_orthogonality", "statistics", "skip", f"only {n} dates with a partial IC (need {MIN_DATES})", {"n_dates": n})
    lag = nw_lag(n) + horizon - 1
    raw_ic, _, raw_t = newey_west_t(raw, lag)
    p_ic, _, p_t = newey_west_t(part, lag)
    kept = float(p_ic / raw_ic) if raw_ic > 0 and np.isfinite(p_ic) else None
    details = {"raw_ic": raw_ic, "raw_t": raw_t, "partial_ic": p_ic, "partial_t": p_t, "share_kept": kept,
               "n_dates": n, "existing": list(existing), "horizon": int(horizon), "nw_lag": lag}
    text = f"partial rank IC {p_ic:.4f} (t={p_t:.1f}) vs raw {raw_ic:.4f} (t={raw_t:.1f})"
    if kept is not None:
        text += f", keeping {kept:.0%} of the raw IC after removing {len(xs)} existing score(s)"
    if raw_t >= T_SIGNIFICANT and not p_t >= T_SIGNIFICANT:
        return check("signal_orthogonality", "statistics", "warn", f"{text}: the new score repeats signals you already have", details)
    return check("signal_orthogonality", "statistics", "info", text, details)


__all__ = ["load_existing_scores", "signal_orthogonality"]
