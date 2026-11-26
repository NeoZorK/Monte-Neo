"""Breadth-aware significance for cross-sectional portfolios: many names are not many independent bets.

The fundamental law says ``IR ~ IC * sqrt(breadth)``. Breadth is the number of *independent* bets, not the number of names:
correlated names (one market factor drives most coins) count once. Here the effective number of bets is the participation
ratio of the eigenvalues of the return correlation matrix, ``(sum l)^2 / sum l^2``, always between 1 and the number of names.
The reported significance is the smaller of two numbers, the Newey-West t of the information-coefficient series and
``IC * sqrt(n_eff * T)``, so the breadth can never make a result look better than the series itself says.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.alpha.multiple_testing import _nw_lag
from monte_neo.verify.checks import check

MIN_DATES, MIN_NAMES = 30, 3
T_BAR = 2.0


def effective_breadth(returns: pd.DataFrame | np.ndarray) -> dict[str, Any]:
    """Effective number of independent bets of a ``(dates, names)`` return table (names without variance are dropped)."""
    x = np.asarray(returns, dtype=float)
    if x.ndim != 2 or x.shape[0] < MIN_DATES or x.shape[1] < 1:
        raise ValueError(f"effective_breadth needs a (dates, names) table with at least {MIN_DATES} dates")
    # names listed later have NaN before their first bar: keep every name with enough finite returns, correlate pairwise
    x = x[:, np.isfinite(x).sum(axis=0) >= MIN_DATES]
    x = x[:, np.nanstd(x, axis=0) > 0] if x.shape[1] else x
    n = x.shape[1]
    if n < 2:
        return {"n_names": int(n), "n_eff": float(max(n, 1)), "mean_abs_corr": None, "dates": int(x.shape[0])}
    corr = pd.DataFrame(x).corr(min_periods=MIN_DATES).fillna(0.0).to_numpy(copy=True)
    np.fill_diagonal(corr, 1.0)
    lam = np.clip(np.linalg.eigvalsh(corr), 0.0, None)
    n_eff = float(lam.sum() ** 2 / np.sum(lam**2))
    off = corr[~np.eye(n, dtype=bool)]
    return {"n_names": int(n), "n_eff": float(min(max(n_eff, 1.0), n)), "mean_abs_corr": float(np.abs(off).mean()), "dates": int(x.shape[0])}


def cross_sectional_ic(signal: pd.DataFrame, forward_returns: pd.DataFrame, *, min_names: int = MIN_NAMES) -> pd.Series:
    """Spearman correlation of the signal with the next-period return, one value per date (dates with too few names are dropped)."""
    sig, fwd = signal.align(forward_returns, join="inner")
    out = {}
    for t in sig.index:
        pair = pd.concat([sig.loc[t], fwd.loc[t]], axis=1).dropna()
        if len(pair) >= min_names and pair.iloc[:, 0].nunique() > 1 and pair.iloc[:, 1].nunique() > 1:
            out[t] = float(pair.iloc[:, 0].rank().corr(pair.iloc[:, 1].rank()))
    return pd.Series(out, dtype=float)


def _nw_t(x: np.ndarray) -> float:
    n = len(x)
    d = x - x.mean()
    lag = min(_nw_lag(n), n - 2)
    var = float(d @ d) / n
    for k in range(1, lag + 1):
        var += 2.0 * (1.0 - k / (lag + 1.0)) * float(d[k:] @ d[:-k]) / n
    return float(x.mean() / math.sqrt(var / n)) if var > 0 else 0.0


def breadth_report(signal: pd.DataFrame, forward_returns: pd.DataFrame, asset_returns: pd.DataFrame | None = None, *, periods_per_year: float = 252.0) -> dict[str, Any]:
    """IC series, effective breadth and the significance that does not count correlated names as independent bets.

    Args:
        signal: Dates x names signal known at the date.
        forward_returns: Dates x names return earned after the date.
        asset_returns: Dates x names returns used for the correlation (default: ``forward_returns``).
        periods_per_year: Rebalances per year, to annualise the implied information ratio.

    Raises:
        ValueError: Fewer than 30 dates with an IC.
    """
    ic = cross_sectional_ic(signal, forward_returns)
    if len(ic) < MIN_DATES:
        raise ValueError(f"only {len(ic)} dates have an IC, at least {MIN_DATES} are needed")
    br = effective_breadth(asset_returns if asset_returns is not None else forward_returns)
    n_names, n_eff, t = br["n_names"], br["n_eff"], len(ic)
    mean = float(ic.mean())
    t_ic = _nw_t(ic.to_numpy())
    z_breadth = mean * math.sqrt(n_eff * t)
    z_naive = mean * math.sqrt(n_names * t)
    significance = min(t_ic, z_breadth)
    ann = math.sqrt(periods_per_year)
    return {"n_dates": int(t), "ic_mean": mean, "ic_sd": float(ic.std(ddof=1)), "ic_t_newey_west": t_ic, **br,
            "z_breadth": z_breadth, "z_naive": z_naive, "significance": significance, "inflation_if_names_were_independent": float(z_naive / z_breadth) if z_breadth else None,
            "ir_per_period_effective": mean * math.sqrt(n_eff), "ir_annual_effective": mean * math.sqrt(n_eff) * ann,
            "ir_annual_naive": mean * math.sqrt(n_names) * ann, "bar": T_BAR}


def _names_text(rep: dict[str, Any]) -> str:
    n = int(rep["n_names"])
    if n < 2:
        return f"{n} name{'' if n == 1 else 's'} with enough returns to measure breadth (counted as 1 bet)"
    return f"{n} names act like {rep['n_eff']:.1f} independent bets"


def breadth_row(rep: dict[str, Any]) -> dict[str, Any]:
    """Check row ``breadth_significance``: warn when the result is significant only if names were independent bets."""
    sig, naive = rep["significance"], rep["z_naive"]
    body = (f"IC {rep['ic_mean']:+.3f} over {rep['n_dates']} dates; {_names_text(rep)}; "
            f"significance {sig:.2f} (naive, names independent: {naive:.2f})")
    if sig >= T_BAR:
        return check("breadth_significance", "statistics", "pass", body, rep)
    if naive >= T_BAR:
        return check("breadth_significance", "statistics", "warn", body + ": significant only if the names were independent bets", rep)
    return check("breadth_significance", "statistics", "warn", body + ": not significant", rep)


__all__ = ["breadth_report", "breadth_row", "cross_sectional_ic", "effective_breadth"]
