"""Family H, sequential part: alpha-death monitor (CUSUM and SPRT) and the live track needed."""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check
from monte_neo.verify.confidence import min_track_record_bars

CUSUM_H = 4.0  # alarm level in log-likelihood units: h / shift standard deviations of one bar (ARL0 in the thousands of bars)
CUSUM_K = 0.5  # reference value, as a share of the shift being detected (expected mean -> 0)
SPRT_ALPHA = 0.05
SPRT_BETA = 0.05
MIN_LIVE_BARS = 10


def _stamp(index: pd.Index, i: int) -> str:
    return str(index[i])


def cusum_alarm(r: np.ndarray, mu: float, sigma: float, *, h: float = CUSUM_H, k: float = CUSUM_K) -> tuple[int | None, float]:
    """One-sided CUSUM for a drop of the mean from ``mu`` to zero.

    The returns are standardised by ``sigma``; the statistic accumulates the shortfall ``(mu - r) / sigma`` minus the
    reference ``k * shift`` (``k`` of the standardised shift ``mu / sigma``), floored at zero, and is scaled by the
    shift so that ``h`` is a log-likelihood level (a plain 4-sigma level would fire on noise when the shift is small).
    Returns the first position where it exceeds ``h`` (None if never) and its last value.
    """
    shift = mu / sigma
    s = 0.0
    for i, x in enumerate(r):
        s = max(0.0, s + shift * ((mu - float(x)) / sigma - k * shift))
        if s > h:
            return i, s
    return None, s


def sprt_alarm(
    r: np.ndarray, mu: float, sigma: float, *, alpha: float = SPRT_ALPHA, beta: float = SPRT_BETA
) -> tuple[int | None, float, int]:
    """Repeated Gaussian SPRT: "mean = mu" against "mean = 0".

    The log-likelihood ratio (zero over expected) moves up when returns fall short. Crossing ``ln((1-beta)/alpha)``
    is an alarm (alpha is dead); crossing ``ln(beta/(1-alpha))`` accepts "as expected" and restarts the test.
    Returns the first alarm position (None), the last ratio, and the number of "as expected" acceptances.
    """
    upper = math.log((1.0 - beta) / alpha)
    lower = math.log(beta / (1.0 - alpha))
    llr, accepted = 0.0, 0
    for i, x in enumerate(r):
        llr += mu * (mu / 2.0 - float(x)) / (sigma * sigma)
        if llr >= upper:
            return i, llr, accepted
        if llr <= lower:
            llr, accepted = 0.0, accepted + 1
    return None, llr, accepted


def alpha_death_monitor(live: pd.Series, expect: dict[str, float], haircut: float) -> dict[str, Any]:
    """``alpha_death_monitor`` (statistics): CUSUM and SPRT of live returns against the haircut backtest mean."""
    r = live.to_numpy(dtype=np.float64)
    mu = haircut * expect["mean"]
    sigma = expect["std"]
    if r.size < MIN_LIVE_BARS or not mu > 0.0 or not sigma > 0.0:
        why = "fewer than 10 live bars" if r.size < MIN_LIVE_BARS else "the backtest mean is not positive"
        return check("alpha_death_monitor", "statistics", "skip", f"alpha death monitor: skipped, {why}")
    c_at, c_last = cusum_alarm(r, mu, sigma)
    s_at, s_last, accepted = sprt_alarm(r, mu, sigma)
    details = {
        "expected_mean_per_bar": mu, "backtest_mean_per_bar": expect["mean"], "haircut": haircut, "sigma_per_bar": sigma,
        "cusum_h": CUSUM_H, "cusum_k": CUSUM_K, "cusum_last": round(c_last, 3), "cusum_alarm_date": None if c_at is None else _stamp(live.index, c_at),
        "sprt_alpha": SPRT_ALPHA, "sprt_beta": SPRT_BETA, "sprt_llr_last": round(s_last, 3),
        "sprt_alarm_date": None if s_at is None else _stamp(live.index, s_at), "sprt_accepted_expected": accepted,
        "live_mean_per_bar": float(np.mean(r)),
    }
    if c_at is not None or s_at is not None:
        hit = [f"{n} on {details[n.lower() + '_alarm_date']}" for n, a in (("CUSUM", c_at), ("SPRT", s_at)) if a is not None]
        return check("alpha_death_monitor", "statistics", "warn", "alpha may be dead: " + ", ".join(hit), details)
    return check(
        "alpha_death_monitor", "statistics", "info",
        f"no alarm: CUSUM {c_last:.2f} of {CUSUM_H:g}, SPRT ratio {s_last:.2f}, live mean {np.mean(r):.5f} vs expected {mu:.5f} per bar", details,
    )


def live_track_needed(live_bars: int, expect: dict[str, float], haircut: float) -> dict[str, Any]:
    """``live_track_needed`` (statistics, info): live bars needed to tell the expected Sharpe from zero at 95 %."""
    sr = haircut * expect["mean"] / expect["std"] if expect["std"] > 0.0 else 0.0
    need = min_track_record_bars(sr, expect.get("skew", 0.0), expect.get("kurt", 3.0))
    if need is None:
        return check("live_track_needed", "statistics", "skip", "live track needed: the expected Sharpe is not positive")
    need_bars = int(math.ceil(need))
    left = max(0, need_bars - live_bars)
    z = NormalDist().inv_cdf(0.95)
    details = {"expected_sharpe_per_bar": sr, "need_bars": need_bars, "have_bars": live_bars, "bars_left": left, "z": z}
    text = "enough live bars" if left == 0 else f"{left} more bars"
    return check("live_track_needed", "statistics", "info", f"{need_bars} live bars tell the expected Sharpe from zero at 95 %: have {live_bars}, {text}", details)


__all__ = ["alpha_death_monitor", "cusum_alarm", "live_track_needed", "sprt_alarm"]
