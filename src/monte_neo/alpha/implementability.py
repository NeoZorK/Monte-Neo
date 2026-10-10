"""Family D implementability checks: impact, capacity, shorts, participation."""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np

from monte_neo.alpha.implementability_common import (
    adv_value,
    ann_return,
    ann_sharpe,
    as_2d,
    clean_weights,
    gross_series,
    has_volume,
    periods_per_year,
    simple_returns,
    trailing_prior,
    weight_changes,
)
from monte_neo.verify.checks import check

CATEGORY = "economics"
IMPACT_WARN_SHARE = 0.5
ILLIQUID_SHORT_WARN = 0.30
BORROW_WARN_SHARE = 0.50
DEFAULT_BORROW_BPS = 300.0
_NO_VOLUME = "volume is missing: market impact and liquidity cannot be estimated"


def _net_series(
    w: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    aum: float,
    impact_coef: float,
    commission_bps: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-bar gross, commission and square-root impact cost (all causal)."""
    ret = simple_returns(close)
    gross = gross_series(w, ret)
    dw = np.abs(weight_changes(w))
    vol = np.nan_to_num(trailing_prior(ret, "std"), nan=0.0)
    adv = adv_value(close, volume)
    with np.errstate(divide="ignore", invalid="ignore"):
        frac = impact_coef * vol * np.sqrt(dw * aum / adv)
    frac = np.minimum(np.nan_to_num(frac, nan=0.0), 1.0)
    impact = (dw * frac).sum(axis=1)
    commission = dw.sum(axis=1) * commission_bps / 1e4
    return gross, commission, impact


def _prep(weights: Any, close: Any, volume: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return clean_weights(weights), as_2d(close), as_2d(volume)


def market_impact(
    weights: Any,
    close: Any,
    volume: Any,
    timestamps: Any,
    aum: float,
    impact_coef: float = 1.0,
    commission_bps: float = 1.0,
) -> dict[str, Any]:
    """Square-root market impact at a target AUM.

    Cost per unit traded = ``impact_coef * sigma * sqrt(traded_value / ADV)`` with a
    trailing 20-bar volatility and ADV known before the bar. Fails if the net annualised
    return is not positive, warns if impact eats more than half of the gross return.

    Args:
        weights: (T, N) target weights, NaN = 0.
        close: (T, N) prices.
        volume: (T, N) units traded per bar, or None (skip).
        timestamps: length-T timestamps for annualisation.
        aum: Target capital in quote currency.
        impact_coef: Multiplier of the square-root law.
        commission_bps: Commission per unit traded, in bps.

    Returns:
        A check row with id ``market_impact``.
    """
    if not has_volume(volume):
        return check("market_impact", CATEGORY, "skip", _NO_VOLUME, {"reason": "no_volume"})
    w, c, v = _prep(weights, close, volume)
    ppy = periods_per_year(timestamps)
    gross, comm, imp = _net_series(w, c, v, aum, impact_coef, commission_bps)
    g_ann, c_ann, i_ann = ann_return(gross, ppy), ann_return(comm, ppy), ann_return(imp, ppy)
    net_ann = g_ann - c_ann - i_ann
    share = i_ann / g_ann if g_ann > 0.0 else None
    if net_ann <= 0.0:
        status = "fail"
    elif share is not None and share > IMPACT_WARN_SHARE:
        status = "warn"
    else:
        status = "pass"
    details = {
        "aum": aum,
        "gross_annual_return": g_ann,
        "commission_annual": c_ann,
        "impact_annual": i_ann,
        "net_annual_return": net_ann,
        "impact_share_of_gross": share,
        "net_sharpe": ann_sharpe(gross - comm - imp, ppy),
    }
    summary = f"at AUM {aum:.3g}: gross {g_ann:.2%}, impact {i_ann:.2%}, net {net_ann:.2%} per year"
    return check("market_impact", CATEGORY, status, summary, details)


def capacity_curve(
    weights: Any,
    close: Any,
    volume: Any,
    timestamps: Any,
    impact_coef: float = 1.0,
    commission_bps: float = 1.0,
    aum_min: float = 1e5,
    aum_max: float = 1e10,
    points: int = 15,
) -> dict[str, Any]:
    """Net Sharpe on a log grid of AUM; AUM where it halves and where it reaches zero.

    Returns:
        A check row with id ``capacity_curve`` (status ``info``); ``details["curve"]``
        lists ``{"aum", "net_sharpe", "net_annual_return"}`` for plotting.
    """
    if not has_volume(volume):
        return check("capacity_curve", CATEGORY, "skip", _NO_VOLUME, {"reason": "no_volume"})
    w, c, v = _prep(weights, close, volume)
    ppy = periods_per_year(timestamps)
    curve = []
    for aum in np.geomspace(aum_min, aum_max, points):
        gross, comm, imp = _net_series(w, c, v, float(aum), impact_coef, commission_bps)
        net = gross - comm - imp
        curve.append({"aum": float(aum), "net_sharpe": ann_sharpe(net, ppy), "net_annual_return": ann_return(net, ppy)})
    s0 = curve[0]["net_sharpe"]
    half = next((p["aum"] for p in curve if s0 > 0 and p["net_sharpe"] <= 0.5 * s0), None)
    zero = next((p["aum"] for p in curve if p["net_sharpe"] <= 0.0), None)
    if s0 <= 0:
        summary = "net Sharpe is not positive even at the smallest AUM"
    elif zero is None:
        summary = f"net Sharpe stays positive up to {aum_max:.3g}" + (f"; halves at {half:.3g}" if half else "")
    else:
        summary = f"net Sharpe halves at AUM {half:.3g} and reaches zero at {zero:.3g}"
    return check("capacity_curve", CATEGORY, "info", summary, {"curve": curve, "aum_half": half, "aum_zero": zero})


def short_feasibility(
    weights: Any,
    close: Any,
    volume: Any,
    timestamps: Any = None,
    borrow_bps_per_year: float | None = None,
    illiquid_quantile: float = 0.2,
) -> dict[str, Any]:
    """Share of short exposure in the least liquid names and borrow cost vs short profit.

    Warns if more than 30 % of short gross sits in the least liquid quantile (by trailing
    ADV value, cross-sectionally per bar) or the borrow cost exceeds 50 % of the short-leg
    profit. Borrow defaults to a conservative 300 bps per year.
    """
    if not has_volume(volume):
        return check("short_feasibility", CATEGORY, "skip", _NO_VOLUME, {"reason": "no_volume"})
    w, c, v = _prep(weights, close, volume)
    ppy = periods_per_year(timestamps)
    borrow = DEFAULT_BORROW_BPS if borrow_bps_per_year is None else float(borrow_bps_per_year)
    held = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
    short = np.maximum(-held, 0.0)
    if short.sum() <= 0.0:
        return check("short_feasibility", CATEGORY, "pass", "no short exposure", {"short_gross_mean": 0.0})
    adv = adv_value(c, v)
    if c.shape[1] > 1:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cutoff = np.nanquantile(adv, illiquid_quantile, axis=1, keepdims=True)
    else:
        cutoff = np.full((c.shape[0], 1), -np.inf)
    illiquid = np.isfinite(adv) & (adv <= cutoff)
    ill_share = float((short * illiquid).sum() / short.sum())
    profit_ann = ann_return((-short * simple_returns(c)).sum(axis=1), ppy)
    cost_ann = float(short.sum(axis=1).mean() * borrow / 1e4)
    cost_share = cost_ann / profit_ann if profit_ann > 0.0 else None
    borrow_heavy = cost_ann > 0.0 and (profit_ann <= 0.0 or (cost_share or 0.0) > BORROW_WARN_SHARE)
    warn = ill_share > ILLIQUID_SHORT_WARN or borrow_heavy
    details = {
        "illiquid_short_share": ill_share,
        "borrow_bps_per_year": borrow,
        "borrow_cost_annual": cost_ann,
        "short_leg_annual_return": profit_ann,
        "borrow_share_of_short_profit": cost_share,
    }
    summary = f"{ill_share:.0%} of short exposure in the least liquid {illiquid_quantile:.0%}; borrow {cost_ann:.2%}/yr vs short-leg profit {profit_ann:.2%}/yr"
    return check("short_feasibility", CATEGORY, "warn" if warn else "pass", summary, details)


def participation_limit(weights: Any, close: Any, volume: Any, aum: float, limit: float = 0.05) -> dict[str, Any]:
    """Traded value over the bar's traded value per symbol-bar.

    Warns if the 95th percentile exceeds ``limit``, fails above ``4 * limit``.
    """
    if not has_volume(volume):
        return check("participation_limit", CATEGORY, "skip", _NO_VOLUME, {"reason": "no_volume"})
    w, c, v = _prep(weights, close, volume)
    traded = np.abs(weight_changes(w)) * aum
    bar_value = c * v
    ok = (traded > 0.0) & np.isfinite(bar_value) & (bar_value > 0.0)
    if not ok.any():
        return check("participation_limit", CATEGORY, "pass", "no trades with a known bar volume", {})
    part = traded[ok] / bar_value[ok]
    p95, pmax = float(np.percentile(part, 95)), float(part.max())
    status = "fail" if p95 > 4 * limit else ("warn" if p95 > limit else "pass")
    summary = f"participation p95 {p95:.2%}, max {pmax:.2%} of bar volume (limit {limit:.0%})"
    return check("participation_limit", CATEGORY, status, summary, {"p95": p95, "max": pmax, "limit": limit, "aum": aum, "trades": int(ok.sum())})
