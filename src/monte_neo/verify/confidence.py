"""How sure are we? Bootstrap confidence intervals and the minimum track record length.

A Sharpe ratio measured on a finite sample is an estimate. Two context checks say how far to
trust it; both are ``info`` rows and never change the verdict (the Deflated Sharpe does that):

* **Circular block bootstrap** of the per-bar returns: the 95% interval of the annualized
  Sharpe ratio and of the total return, plus the share of resamples with a positive Sharpe.
  Blocks (length about the cube root of the sample) keep the autocorrelation of returns.
  Resampling uses prefix sums, so 1000 resamples of 200 000 bars take milliseconds; the seed
  is fixed, so a certificate can be reproduced.
* **Minimum Track Record Length** (Bailey and Lopez de Prado): how many bars the observed
  Sharpe needs before it is significantly positive at 95%.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any

import numpy as np

from monte_neo.verify.checks import check

BOOTSTRAP_SAMPLES = 1000
BOOTSTRAP_SEED = 20260929
MIN_BOOTSTRAP_BARS = 60
LEVEL = 0.95
_NORMAL = NormalDist()


def block_length(n_obs: int) -> int:
    """Block length: the cube root of the sample, at least 2."""
    return max(2, round(n_obs ** (1.0 / 3.0)))


def bootstrap_ci(
    rets: np.ndarray, periods_per_year: float, *, samples: int = BOOTSTRAP_SAMPLES, level: float = LEVEL, seed: int = BOOTSTRAP_SEED
) -> dict[str, Any]:
    """Circular block bootstrap interval of the annualized Sharpe and of the total return."""
    r = np.asarray(rets, dtype=np.float64)
    r = r[np.isfinite(r)]
    n = r.size
    length = block_length(n)
    blocks = n // length
    if n < MIN_BOOTSTRAP_BARS or blocks < 5:
        return {}
    ext = np.concatenate([r, r[: length - 1]])  # a block may wrap around the end
    log_ext = np.log1p(np.clip(ext, -0.999999, None))
    c1, c2, cl = (np.concatenate([[0.0], np.cumsum(a)]) for a in (ext, ext * ext, log_ext))
    starts = np.random.default_rng(seed).integers(0, n, size=(int(samples), blocks))
    total = blocks * length

    def block_sums(prefix: np.ndarray) -> np.ndarray:
        return (prefix[starts + length] - prefix[starts]).sum(axis=1)

    mean = block_sums(c1) / total
    var = np.maximum(block_sums(c2) / total - mean * mean, 0.0) * total / (total - 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        sharpe = np.where(var > 1e-30, mean / np.sqrt(var), 0.0) * math.sqrt(max(periods_per_year, 1.0))
    growth = np.expm1(block_sums(cl) * n / total)  # compounded over the original length
    lo, hi = (1.0 - level) / 2.0 * 100.0, (1.0 + level) / 2.0 * 100.0
    return {
        "method": "circular block bootstrap",
        "block_bars": int(length),
        "samples": int(samples),
        "level": float(level),
        "sharpe_annualized": [round(float(v), 3) for v in np.percentile(sharpe, [lo, hi])],
        "total_return": [round(float(v), 4) for v in np.percentile(growth, [lo, hi])],
        "prob_sharpe_positive": round(float(np.mean(sharpe > 0.0)), 3),
    }


def min_track_record_bars(sr: float, skew: float, kurt: float, *, sr_benchmark: float = 0.0, confidence: float = LEVEL) -> float | None:
    """Bars needed for the Sharpe ``sr`` (per bar) to beat ``sr_benchmark`` with ``confidence``; None if it does not."""
    if not math.isfinite(sr) or sr <= sr_benchmark:
        return None
    z = _NORMAL.inv_cdf(confidence)
    spread = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    return float(1.0 + max(spread, 1e-12) * (z / (sr - sr_benchmark)) ** 2)


def track_record(dsr: dict[str, Any], periods_per_year: float) -> dict[str, Any]:
    """Minimum track record length for the strategy's Sharpe, from its own skew and kurtosis."""
    bars = min_track_record_bars(float(dsr["sharpe_per_bar"]), float(dsr["skew"]), float(dsr["kurtosis"]))
    return {
        "have_bars": int(dsr["n_obs"]),
        "need_bars": None if bars is None else int(math.ceil(bars)),
        "need_years": None if bars is None else round(bars / max(periods_per_year, 1.0), 2),
        "confidence": LEVEL,
    }


def confidence_row(ci: dict[str, Any]) -> dict[str, Any]:
    """``sharpe_confidence``: the interval of the Sharpe ratio (context, never changes the verdict)."""
    if not ci:
        return check("sharpe_confidence", "statistics", "skip", "too few bars for a bootstrap interval")
    lo, hi = ci["sharpe_annualized"]
    r_lo, r_hi = ci["total_return"]
    summary = (
        f"Sharpe {ci['level']:.0%} interval {lo:+.2f} to {hi:+.2f} (return {r_lo:+.1%} to {r_hi:+.1%}); "
        f"{ci['prob_sharpe_positive']:.0%} of resamples have a positive Sharpe"
    )
    return check("sharpe_confidence", "statistics", "info", summary, ci)


def track_record_row(info: dict[str, Any]) -> dict[str, Any]:
    """``track_record``: how much history the Sharpe needs to be believed (context, never changes the verdict)."""
    if info["need_bars"] is None:
        return check("track_record", "statistics", "info", "the Sharpe is not positive: no history length makes it significant", info)
    enough = info["have_bars"] >= info["need_bars"]
    summary = (
        f"needs {info['need_bars']:,} bars (about {info['need_years']:g} years) to be positive at {info['confidence']:.0%}; "
        f"has {info['have_bars']:,}" + ("" if enough else ": not enough history yet")
    )
    return check("track_record", "statistics", "info", summary, info)


__all__ = ["block_length", "bootstrap_ci", "confidence_row", "min_track_record_bars", "track_record", "track_record_row"]
