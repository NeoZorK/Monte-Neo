"""Shared causal helpers for the implementability checks (family D)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.stats import infer_periods_per_year

WINDOW = 20


def clean_weights(weights: Any) -> np.ndarray:
    """Float (T, N) weights with NaN treated as zero."""
    w = np.nan_to_num(np.asarray(weights, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    return w.reshape(-1, 1) if w.ndim == 1 else w


def as_2d(x: Any) -> np.ndarray:
    """Float (T, N) array, NaN kept."""
    a = np.asarray(x, dtype=np.float64)
    return a.reshape(-1, 1) if a.ndim == 1 else a


def simple_returns(close: np.ndarray) -> np.ndarray:
    """Per-bar simple returns, first row and gaps set to zero."""
    ret = np.zeros_like(close)
    with np.errstate(divide="ignore", invalid="ignore"):
        ret[1:] = close[1:] / close[:-1] - 1.0
    return np.nan_to_num(ret, nan=0.0, posinf=0.0, neginf=0.0)


def trailing_prior(x: np.ndarray, kind: str = "mean", window: int = WINDOW) -> np.ndarray:
    """Trailing mean or std over bars up to ``t - 1`` (strictly causal)."""
    roll = pd.DataFrame(x).rolling(window, min_periods=max(3, window // 4))
    out = roll.mean() if kind == "mean" else roll.std()
    return out.shift(1).to_numpy(dtype=np.float64)


def adv_value(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """Trailing average traded value known before each bar (NaN where unknown/zero)."""
    adv = trailing_prior(close * volume, "mean")
    return np.where(adv > 0.0, adv, np.nan)


def weight_changes(w: np.ndarray) -> np.ndarray:
    """``dw[t]`` = trade filled on bar t (decided at t-1): ``w[t-1] - w[t-2]``."""
    held = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
    return np.diff(np.vstack([np.zeros((1, w.shape[1])), held]), axis=0)


def gross_series(w: np.ndarray, ret: np.ndarray) -> np.ndarray:
    """Portfolio return per bar: ``sum(w[t-1] * ret[t])``."""
    held = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
    return (held * ret).sum(axis=1)


def ann_return(r: np.ndarray, ppy: float) -> float:
    """Arithmetic annualised return."""
    return float(np.mean(r) * ppy) if r.size else 0.0


def ann_sharpe(r: np.ndarray, ppy: float) -> float:
    """Annualised Sharpe (zero risk-free); 0 for flat series."""
    sd = float(np.std(r, ddof=1)) if r.size > 1 else 0.0
    return float(np.mean(r) / sd * np.sqrt(ppy)) if sd > 1e-15 else 0.0


def periods_per_year(timestamps: Any) -> float:
    """Bars per year inferred from timestamps."""
    return infer_periods_per_year(timestamps)


def has_volume(volume: Any) -> bool:
    """True if ``volume`` carries at least one positive finite value."""
    if volume is None:
        return False
    v = np.asarray(volume, dtype=np.float64)
    return bool(np.any(np.isfinite(v) & (v > 0.0)))
