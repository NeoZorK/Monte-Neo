"""Family A (signal power), part 2: long/short legs, breadth, placebo, selection vs timing."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.alpha._core import leg_weights, quantile_index, sharpe
from monte_neo.alpha.panel import Panel
from monte_neo.verify.checks import check

SHORT_SHARE_WARN = 0.70
CLAIM_FACTOR = 2.0
P_THRESHOLD = 0.10
MIN_DATES = 20


def _legs(panel: Panel, fwd: np.ndarray, q: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(long leg, short leg, spread, weights, valid) per date; dates with fewer than q names are NaN."""
    valid = np.isfinite(panel.scores) & np.isfinite(fwd)
    qi = quantile_index(panel.scores, valid, q)
    w = leg_weights(qi, q)
    r0 = np.nan_to_num(fwd)
    n = valid.sum(axis=1)
    top = np.where(qi == q - 1, w, 0.0)
    bot = np.where(qi == 0, -w, 0.0)
    uni = (r0 * valid).sum(axis=1) / np.maximum(n, 1)
    long_leg = (top * r0).sum(axis=1) - uni
    short_leg = uni - (bot * r0).sum(axis=1)
    bad = n < q
    w = w * (~bad)[:, None]
    for a in (long_leg, short_leg):
        a[bad] = np.nan
    return long_leg, short_leg, long_leg + short_leg, w, valid


def check_long_short_legs(panel: Panel, fwd: np.ndarray, quantiles: int = 5) -> dict[str, Any]:
    """A4: share of the top-minus-bottom spread earned by the short leg.

    Args:
        panel: Aligned scores and prices.
        fwd: Forward returns (targets only).
        quantiles: Number of buckets.

    Returns:
        Check ``long_short_legs`` (category economics): warn if more than 70% of a positive
        spread comes from the short leg, which is often not implementable.
    """
    lg, sh, sp, _, _ = _legs(panel, fwd, quantiles)
    ml, ms, mt = (float(np.nanmean(x)) if np.isfinite(x).any() else float("nan") for x in (lg, sh, sp))
    if not np.isfinite(mt):
        return check("long_short_legs", "economics", "skip", "no dates with enough names for the legs")
    share = ms / mt if mt > 0 else float("nan")
    details = {"long_leg_mean": ml, "short_leg_mean": ms, "spread_mean": mt, "short_share": share}
    if mt <= 0:
        return check("long_short_legs", "economics", "info", "the top-minus-bottom spread is not positive; no profit to split", details)
    if share > SHORT_SHARE_WARN:
        return check("long_short_legs", "economics", "warn", f"{share:.0%} of the spread profit comes from the short leg: shorts are often not implementable (borrow, bans, microcaps)", details)
    return check("long_short_legs", "economics", "pass", f"short leg earns {share:.0%} of the spread; long leg {1 - share:.0%}", details)


def check_breadth_consistency(panel: Panel, mean_ic: float, horizon: int, claimed_ir: float | None) -> dict[str, Any]:
    """A5: compare a claimed annual IR with the fundamental law IR = IC * sqrt(breadth per year).

    Args:
        panel: Aligned scores and prices.
        mean_ic: Mean rank IC from check A1.
        horizon: Forward-return horizon in bars.
        claimed_ir: Claimed annualised information ratio, or None.

    Returns:
        Check ``breadth_consistency``: skip without a claim, warn if the claim exceeds 2x implied.
    """
    if claimed_ir is None:
        return check("breadth_consistency", "statistics", "skip", "no claimed IR given (--claim-ir)")
    names = float(np.nanmean(np.isfinite(panel.scores).sum(axis=1)))
    breadth = names * panel.periods_per_year / horizon
    implied = float(mean_ic * np.sqrt(breadth)) if np.isfinite(mean_ic) else float("nan")
    details = {"claimed_ir": claimed_ir, "implied_ir": implied, "mean_ic": mean_ic, "breadth_per_year": breadth}
    if not np.isfinite(implied) or implied <= 0 or claimed_ir > CLAIM_FACTOR * implied:
        return check("breadth_consistency", "statistics", "warn", f"claimed IR {claimed_ir:.2f} vs {implied:.2f} implied by IC and breadth: the claim is more than {CLAIM_FACTOR:.0f}x the fundamental law", details)
    return check("breadth_consistency", "statistics", "pass", f"claimed IR {claimed_ir:.2f} is consistent with the {implied:.2f} implied by IC and breadth", details)


def _placebo_sharpes(w: np.ndarray, fwd: np.ndarray, valid: np.ndarray, rng: np.random.Generator, n: int) -> np.ndarray:
    """Spread Sharpe of ``n`` within-date permutations of the returns among the valid names."""
    order = np.argsort(~valid, axis=1, kind="stable")  # valid columns first
    wc = np.take_along_axis(w, order, axis=1)
    rc = np.take_along_axis(np.where(valid, np.nan_to_num(fwd), 0.0), order, axis=1)
    k = valid.sum(axis=1, keepdims=True)
    slot = np.arange(w.shape[1])[None, :]
    pad = (slot >= k).astype(np.float32) * 2.0
    keep = k.ravel() >= 3
    wc, rc, pad = wc[keep], rc[keep], pad[keep]
    out = np.empty(n)
    for i in range(n):
        perm = np.argsort(rng.random(wc.shape, dtype=np.float32) + pad, axis=1)
        out[i] = sharpe((wc * np.take_along_axis(rc, perm, axis=1)).sum(axis=1))
    return out


def check_signal_placebo(panel: Panel, fwd: np.ndarray, quantiles: int = 5, seed: int = 0, placebos: int = 200) -> dict[str, Any]:
    """A6: does the real long-short spread beat scores permuted across symbols within each date?

    Args:
        panel: Aligned scores and prices.
        fwd: Forward returns (targets only).
        quantiles: Number of buckets.
        seed: Placebo seed.
        placebos: Number of permuted-score placebos.

    Returns:
        Check ``signal_placebo``: fail if p > 0.10 (the construction earns, not the signal).
    """
    _, _, sp, w, valid = _legs(panel, fwd, quantiles)
    if np.isfinite(sp).sum() < MIN_DATES:
        return check("signal_placebo", "statistics", "skip", "too few dates for a placebo test")
    real = sharpe(sp)
    plc = _placebo_sharpes(w, fwd, valid, np.random.default_rng(seed), placebos)
    plc = plc[np.isfinite(plc)]
    p = float((1 + np.sum(plc >= real)) / (len(plc) + 1))
    details = {"real_sharpe_per_period": real, "placebo_mean": float(plc.mean()), "placebo_p95": float(np.percentile(plc, 95)), "p_value": p, "n_placebos": len(plc)}
    if p > P_THRESHOLD:
        why = "the construction earns, not the signal" if real > 0 else "the spread does not earn"
        return check("signal_placebo", "statistics", "fail", f"real spread Sharpe {real:.3f}/period is not above permuted-score placebos (p={p:.3f}): {why}", details)
    return check("signal_placebo", "statistics", "pass", f"real spread Sharpe {real:.3f}/period beats permuted-score placebos (p={p:.3f})", details)


def check_selection_vs_timing(panel: Panel, fwd: np.ndarray, quantiles: int = 5, seed: int = 0, draws: int = 50) -> dict[str, Any]:
    """A7: how much of the spread is cross-sectional selection vs a time-invariant tilt.

    The spread is recomputed with scores shuffled across symbols within a date (selection
    removed) and with whole score rows reassigned to other dates (date alignment removed).

    Args:
        panel: Aligned scores and prices.
        fwd: Forward returns (targets only).
        quantiles: Number of buckets.
        seed: Shuffle seed.
        draws: Shuffles per variant.

    Returns:
        Info check ``selection_vs_timing``.
    """
    _, _, sp, w, valid = _legs(panel, fwd, quantiles)
    ok = np.isfinite(sp)
    if ok.sum() < MIN_DATES:
        return check("selection_vs_timing", "statistics", "skip", "too few dates")
    real = float(np.nanmean(sp))
    rng = np.random.default_rng(seed)
    r0 = np.where(valid, np.nan_to_num(fwd), 0.0)
    # Shuffle across symbols = permute returns among valid names within a date.
    order = np.argsort(~valid, axis=1, kind="stable")
    wc = np.take_along_axis(w, order, axis=1)
    rc = np.take_along_axis(r0, order, axis=1)
    pad = (np.arange(w.shape[1])[None, :] >= valid.sum(axis=1, keepdims=True)).astype(np.float32) * 2.0
    sym = float(np.mean([(wc * np.take_along_axis(rc, np.argsort(rng.random(wc.shape, dtype=np.float32) + pad, axis=1), axis=1)).sum(axis=1)[ok].mean() for _ in range(draws)]))
    # Shuffle across dates = pair each date's weights with another date's returns.
    dat = float(np.mean([(w * r0[rng.permutation(len(w))]).sum(axis=1)[ok].mean() for _ in range(draws)]))
    selection = real - sym
    details = {"spread_mean": real, "shuffle_symbols_mean": sym, "shuffle_dates_mean": dat, "selection_effect": selection,
               "selection_share": selection / real if real > 0 else float("nan"), "timing_or_tilt_residual": dat}
    msg = f"spread {real:.4%}/period; selection effect {selection:.4%}; with dates shuffled {dat:.4%} (a time-invariant tilt or market timing, not stock selection)"
    return check("selection_vs_timing", "statistics", "info", msg, details)
