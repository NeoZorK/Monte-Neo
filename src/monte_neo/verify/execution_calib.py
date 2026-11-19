"""Execution calibration from your own fills: market-impact coefficient, impact decay, participation, maker rebates.

* :func:`calibrate_impact` fits ``slippage_bps = coef * sigma_bps * sqrt(share)`` to a table of real fills by least
  squares through the origin (the square-root law of Almgren, Thum, Hauptmann and Li 2005, Risk 18(7); Toth et al. 2011,
  Phys. Rev. X 1). The fitted ``coef`` replaces the default ``impact_coef=1.0`` of
  :func:`monte_neo.verify.execution.simulate_execution`. The exponent is also fitted freely (log-log) and reported, so
  a square-root law that the fills do not support is visible. A fit on fewer than 30 fills, or with no explanatory
  power, is refused, not guessed.
* :func:`decay_factor` is the transient-impact kernel (used by ``simulate_execution(decay_half_life_bars=...)``) (Obizhaeva and Wang 2013, J. Financial Markets 16(1); Bouchaud
  et al. 2004, Quantitative Finance 4(2)): the price displacement left by earlier fills decays exponentially with a
  half-life in bars; a later fill in the same direction pays on top of it.
* :func:`participation_stats` summarises the share of each bar's volume the fills took.
* :func:`rebate_fee_bps` allows a maker rebate (negative maker fee) only when asked for explicitly, and only inside a
  realistic envelope: rebate at most 1 bp, maker share at most 50 %, adverse selection charged on passive fills, and a
  net fee that never goes below zero (a strategy does not earn from fees).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

MIN_FILLS = 30
MIN_R2 = 0.02
MAX_REBATE_BPS = 1.0
MAX_REBATE_MAKER_SHARE = 0.5
REQUIRED = ("slippage_bps", "sigma_bps", "share")


def calibrate_impact(fills: pd.DataFrame | dict[str, Any]) -> dict[str, Any]:
    """Fit the impact coefficient from fills.

    ``fills`` needs ``slippage_bps`` (cost against the arrival price, positive = paid), ``sigma_bps`` (bar volatility in
    bps) and ``share`` (the fill's share of the bar's volume, 0..1]. Rows with non-finite or non-positive sigma/share are
    dropped and counted.

    Raises:
        ValueError: A missing column, fewer than 30 usable fills, or a fit without explanatory power (R2 under 0.02 or a
            non-positive coefficient).
    """
    df = pd.DataFrame(fills)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"fills need columns {REQUIRED}; missing {missing}")
    x_all = df["sigma_bps"].to_numpy(dtype=np.float64) * np.sqrt(np.clip(df["share"].to_numpy(dtype=np.float64), 0.0, None))
    y_all = df["slippage_bps"].to_numpy(dtype=np.float64)
    ok = np.isfinite(x_all) & np.isfinite(y_all) & (x_all > 0) & (df["share"].to_numpy(dtype=np.float64) <= 1.0)
    x, y = x_all[ok], y_all[ok]
    if x.size < MIN_FILLS:
        raise ValueError(f"only {x.size} usable fills; at least {MIN_FILLS} are needed to calibrate impact")
    coef = float(x @ y / (x @ x))
    resid = y - coef * x
    dof = x.size - 1
    se = float(math.sqrt(float(resid @ resid) / dof / float(x @ x)))
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float(resid @ resid) / ss_tot if ss_tot > 0 else 0.0
    if coef <= 0.0 or r2 < MIN_R2:
        raise ValueError(f"the fills do not support an impact law (coef {coef:.3f}, R2 {r2:.3f}); keep a conservative manual impact_coef")
    positive = y > 0
    share = df["share"].to_numpy(dtype=np.float64)[ok]
    exponent = None
    if positive.sum() >= MIN_FILLS and np.ptp(np.log(share[positive])) > 0.5:
        exponent = float(np.polyfit(np.log(share[positive]), np.log(y[positive] / df["sigma_bps"].to_numpy(dtype=np.float64)[ok][positive]), 1)[0])
    return {"coef": coef, "stderr": se, "ci95": [coef - 1.96 * se, coef + 1.96 * se], "r2": r2, "n_fills": int(x.size),
            "dropped": int((~ok).sum()), "share_exponent": exponent}


def decay_factor(half_life_bars: float) -> float:
    """Per-bar survival of displacement left by earlier fills: ``0.5 ** (1 / half_life)``; half-life 0 means no memory.

    Raises:
        ValueError: A negative half-life.
    """
    if half_life_bars < 0:
        raise ValueError("half_life_bars must be >= 0")
    return 0.0 if half_life_bars == 0 else 0.5 ** (1.0 / half_life_bars)


def participation_stats(traded_value: np.ndarray, bar_value: np.ndarray, assumed: float) -> dict[str, Any]:
    """Share of the bar's traded value taken by the fills: mean, p95, max, and how often ``assumed`` was exceeded."""
    q, v = np.asarray(traded_value, dtype=np.float64), np.asarray(bar_value, dtype=np.float64)
    ok = (q > 0) & (v > 0) & np.isfinite(q) & np.isfinite(v)
    if not ok.any():
        return {"fills": 0, "mean": 0.0, "p95": 0.0, "max": 0.0, "share_above_assumed": 0.0, "assumed": float(assumed)}
    sh = q[ok] / v[ok]
    return {"fills": int(ok.sum()), "mean": float(sh.mean()), "p95": float(np.percentile(sh, 95)), "max": float(sh.max()),
            "share_above_assumed": float(np.mean(sh > assumed)), "assumed": float(assumed)}


def rebate_fee_bps(maker_bps: float, taker_bps: float, maker_share: float, *, adverse_selection_bps: float = 0.0) -> dict[str, Any]:
    """Average per-side fee with a maker rebate (``maker_bps`` may be negative), inside the realism envelope.

    Raises:
        ValueError: Rebate over 1 bp, maker share over 50 %, negative taker fee or adverse selection, or share outside 0..1.
    """
    if maker_bps < -MAX_REBATE_BPS:
        raise ValueError(f"a rebate above {MAX_REBATE_BPS} bp per side is not realistic (got {-maker_bps})")
    if taker_bps < 0 or adverse_selection_bps < 0:
        raise ValueError("taker fee and adverse selection must be >= 0 bps")
    if not 0.0 <= maker_share <= 1.0:
        raise ValueError(f"maker_share must be between 0 and 1, got {maker_share}")
    if maker_bps < 0 and maker_share > MAX_REBATE_MAKER_SHARE:
        raise ValueError(f"with a rebate the maker share is capped at {MAX_REBATE_MAKER_SHARE:.0%}: passive fills face queues and adverse selection")
    raw = maker_bps * maker_share + taker_bps * (1.0 - maker_share) + adverse_selection_bps * maker_share
    return {"fee_bps": max(raw, 0.0), "raw_fee_bps": raw, "floored": raw < 0.0}


__all__ = ["MAX_REBATE_BPS", "MAX_REBATE_MAKER_SHARE", "MIN_FILLS", "calibrate_impact", "decay_factor", "participation_stats", "rebate_fee_bps"]
