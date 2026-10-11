"""Family I: risk of the strategy: market neutrality, concentration, leverage, stress windows and tail risk.

Inputs are plain arrays: strategy returns ``r`` (T,), market returns ``m`` (T,), optional weights ``W`` (T x N, one row
per bar, signed) and bar timestamps. Only numpy, pandas and the standard library are used.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check

BETA_WINDOW = 60
BETA_LIMIT = 0.3
NET_LIMIT = 0.2
MIN_EFFECTIVE = 5.0
MAX_WEIGHT = 0.25

STRESS_WINDOWS: dict[str, tuple[str, str]] = {
    "GFC": ("2008-09-01", "2009-03-31"),
    "Flash crash": ("2010-05-06", "2010-05-06"),
    "Euro crisis": ("2011-08-01", "2011-10-04"),
    "China deval": ("2015-08-18", "2015-08-26"),
    "Volmageddon": ("2018-02-02", "2018-02-09"),
    "Covid": ("2020-02-19", "2020-03-23"),
    "Rates": ("2022-01-01", "2022-10-31"),
    "Crypto winter": ("2022-05-05", "2022-06-18"),
    "FTX": ("2022-11-06", "2022-11-21"),
    "SVB": ("2023-03-08", "2023-03-17"),
}

NEXT_ACTIONS: dict[str, str] = {
    "neutrality": "The strategy is declared neutral but carries market beta or net exposure: hedge the beta, or stop calling it neutral.",
    "concentration": "A few positions carry the book: cap single weights and require a minimum number of positions, or size for the loss of the largest one.",
    "leverage_gross_net": "Check the gross and net jumps: sudden leverage changes are risk that the average hides.",
    "historical_stress_replay": "Read the stress windows: a strategy that loses in the known crises needs a plan for the next one.",
    "tail_risk": "Size the position for the CVaR, the worst month and the longest recovery, not for the average day.",
}


def _skip(check_id: str, category: str, reason: str) -> dict[str, Any]:
    return check(check_id, category, "skip", reason, {})


def neutrality(r: np.ndarray, m: np.ndarray, weights: np.ndarray | None = None, declared_neutral: bool = False) -> dict[str, Any]:
    """I1: rolling 60-bar beta of the strategy to the market and mean net exposure.

    Warns when ``declared_neutral`` and |mean beta| > 0.3 or |mean net| > 0.2; otherwise info.
    """
    if len(r) < BETA_WINDOW + 1:
        return _skip("neutrality", "economics", f"fewer than {BETA_WINDOW + 1} bars for a rolling beta")
    rs, ms = pd.Series(r), pd.Series(m)
    beta = (rs.rolling(BETA_WINDOW).cov(ms) / ms.rolling(BETA_WINDOW).var()).dropna()
    mean_beta = float(beta.mean()) if len(beta) else float("nan")
    mean_net = float(np.mean(np.sum(weights, axis=1))) if weights is not None else None
    details = {"mean_beta": mean_beta, "beta_min": float(beta.min()), "beta_max": float(beta.max()), "mean_net": mean_net, "declared_neutral": declared_neutral}
    s = f"mean rolling beta {mean_beta:.2f}" + (f", mean net exposure {mean_net:.2f}" if mean_net is not None else "")
    if not declared_neutral:
        return check("neutrality", "economics", "info", s, details)
    if abs(mean_beta) > BETA_LIMIT or (mean_net is not None and abs(mean_net) > NET_LIMIT):
        return check("neutrality", "economics", "warn", s + ": declared neutral but is not", details)
    return check("neutrality", "economics", "pass", s, details)


def concentration(weights: np.ndarray) -> dict[str, Any]:
    """I2: per-bar HHI of |W|, effective number of positions 1/HHI and max single weight (warn if median < 5 or max > 0.25)."""
    a = np.abs(weights)
    gross = a.sum(axis=1)
    live = gross > 0
    if not live.any():
        return _skip("concentration", "economics", "no bar holds a position")
    norm = a[live] / gross[live, None]
    hhi = (norm**2).sum(axis=1)
    eff = 1.0 / hhi
    med_eff, max_w = float(np.median(eff)), float(norm.max())
    details = {"median_effective_positions": med_eff, "min_effective_positions": float(eff.min()), "median_hhi": float(np.median(hhi)), "max_weight": max_w}
    s = f"median effective positions {med_eff:.1f}, largest single weight {max_w:.0%}"
    if med_eff < MIN_EFFECTIVE or max_w > MAX_WEIGHT:
        return check("concentration", "economics", "warn", s, details)
    return check("concentration", "economics", "pass", s, details)


def leverage_gross_net(weights: np.ndarray) -> dict[str, Any]:
    """I3: gross and net exposure statistics and the largest bar-to-bar jumps."""
    gross, net = np.abs(weights).sum(axis=1), weights.sum(axis=1)
    jg = float(np.abs(np.diff(gross)).max()) if len(gross) > 1 else 0.0
    jn = float(np.abs(np.diff(net)).max()) if len(net) > 1 else 0.0
    details = {
        "gross_mean": float(gross.mean()), "gross_max": float(gross.max()), "net_mean": float(net.mean()),
        "net_min": float(net.min()), "net_max": float(net.max()), "max_gross_jump": jg, "max_net_jump": jn,
    }
    return check("leverage_gross_net", "economics", "info", f"gross {gross.mean():.2f} (max {gross.max():.2f}), net {net.mean():.2f}; largest gross jump {jg:.2f}", details)


def historical_stress_replay(r: np.ndarray, m: np.ndarray, timestamps: pd.DatetimeIndex) -> dict[str, Any]:
    """I4: strategy and market compounded return inside each named historical stress window present in the data."""
    idx = pd.DatetimeIndex(timestamps)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    rs, ms = pd.Series(np.asarray(r, float), index=idx), pd.Series(np.asarray(m, float), index=idx)
    found: dict[str, Any] = {}
    for name, (a, b) in STRESS_WINDOWS.items():
        mask = (idx >= pd.Timestamp(a)) & (idx < pd.Timestamp(b) + pd.Timedelta(days=1))
        if mask.any():
            found[name] = {"bars": int(mask.sum()), "strategy": float((1 + rs[mask]).prod() - 1), "market": float((1 + ms[mask]).prod() - 1)}
    if not found:
        return _skip("historical_stress_replay", "statistics", "the data overlaps none of the named stress windows")
    worst = min(found, key=lambda k: found[k]["strategy"])
    s = f"{len(found)} stress windows in the data; worst for the strategy: {worst} ({found[worst]['strategy']:.1%} vs market {found[worst]['market']:.1%})"
    return check("historical_stress_replay", "statistics", "info", s, {"windows": found})


def _underwater_runs(equity: np.ndarray) -> list[tuple[int, int]]:
    """(start, end) bar indices of every stretch below the running peak; end is the recovery bar or the last bar."""
    under = equity < np.maximum.accumulate(equity)
    runs, start = [], None
    for i, u in enumerate(under):
        if u and start is None:
            start = i
        elif not u and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(under) - 1))
    return runs


def tail_risk(r: np.ndarray, timestamps: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    """I5: historical VaR/CVaR 95 and 99 (as returns, so CVaR <= VaR), worst bar, worst month, longest drawdown recovery."""
    r = np.asarray(r, float)
    det: dict[str, Any] = {"worst_bar": float(r.min())}
    for level in (95, 99):
        var = float(np.quantile(r, 1 - level / 100))
        det[f"var_{level}"], det[f"cvar_{level}"] = var, float(r[r <= var].mean())
    runs = _underwater_runs(np.cumprod(1.0 + r))
    det["longest_recovery_bars"] = max((b - a for a, b in runs), default=0)
    if timestamps is not None:
        idx = pd.DatetimeIndex(timestamps)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        monthly = (1 + pd.Series(r, index=idx)).groupby(idx.to_period("M")).prod() - 1
        det["worst_month"], det["worst_month_label"] = float(monthly.min()), str(monthly.idxmin())
        det["longest_recovery_days"] = max(((idx[b] - idx[a]).days for a, b in runs), default=0)
    s = f"VaR95 {det['var_95']:.2%}, CVaR95 {det['cvar_95']:.2%}, CVaR99 {det['cvar_99']:.2%}, worst bar {det['worst_bar']:.2%}"
    return check("tail_risk", "statistics", "info", s + f", longest recovery {det['longest_recovery_bars']} bars", det)


def run_risk(
    r: np.ndarray, m: np.ndarray, timestamps: pd.DatetimeIndex, ppy: float,
    weights: np.ndarray | None = None, declared_neutral: bool = False,
) -> list[dict[str, Any]]:
    """Run family I (I1, I2, I3 when weights are given, I4, I5).

    Args:
        r: Strategy returns (T,).
        m: Market returns (T,), e.g. the equal-weight universe mean.
        timestamps: Bar dates (length T).
        ppy: Periods per year (kept for a uniform signature).
        weights: Optional signed weights (T x N).
        declared_neutral: Whether the strategy claims market neutrality.
    """
    r, m = np.asarray(r, float), np.asarray(m, float)
    rows = [neutrality(r, m, weights, declared_neutral)]
    if weights is None:
        why = "no weights given"
        rows += [_skip("concentration", "economics", why), _skip("leverage_gross_net", "economics", why)]
    else:
        w = np.asarray(weights, float)
        rows += [concentration(w), leverage_gross_net(w)]
    rows += [historical_stress_replay(r, m, timestamps), tail_risk(r, timestamps)]
    return rows


__all__ = ["NEXT_ACTIONS", "STRESS_WINDOWS", "concentration", "historical_stress_replay", "leverage_gross_net", "neutrality", "run_risk", "tail_risk"]
