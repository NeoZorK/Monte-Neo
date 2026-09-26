"""Deterministic look-ahead probes that need no access to the strategy's intent.

* Truncation: the signal at bar ``t`` must not change when bars after ``t``
  are removed.
* Perturbation: the signals up to bar ``t`` must not change when bars after
  ``t`` are rewritten (future returns mirrored).
* Implausible accuracy: next-bar direction hit rates far above what real
  edges achieve are almost always leakage.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.ingest import OHLC_COLS, SignalFn, call_signal_fn

MAX_REPORTED = 5


def _checkpoints(n_bars: int, n_checks: int, start: int | None) -> np.ndarray:
    lo = max(2, int(start) if start is not None else n_bars // 10)
    hi = n_bars - 2
    if hi <= lo:
        return np.array([hi], dtype=np.int64) if hi >= 1 else np.zeros(0, dtype=np.int64)
    return np.unique(np.linspace(lo, hi, num=max(1, int(n_checks))).astype(np.int64))


def _status(mismatches: list[dict[str, Any]], checked: int) -> str:
    if checked == 0:
        return "skip"
    return "fail" if mismatches else "pass"


def probe_determinism(fn: SignalFn, df: pd.DataFrame, full: np.ndarray | None = None) -> dict[str, Any]:
    """Two runs on identical input must give identical signals."""
    first = call_signal_fn(fn, df) if full is None else full
    second = call_signal_fn(fn, df)
    diff = np.flatnonzero(first != second)
    return {
        "status": "fail" if diff.size else "pass",
        "differing_bars": int(diff.size),
        "first_differing_bar": int(diff[0]) if diff.size else None,
    }


def probe_truncation(
    fn: SignalFn,
    df: pd.DataFrame,
    *,
    n_checks: int = 24,
    start: int | None = None,
    full: np.ndarray | None = None,
) -> dict[str, Any]:
    """Compare ``signal(df[:t+1])[-1]`` with ``signal(df)[t]`` at checkpoints."""
    sig = call_signal_fn(fn, df) if full is None else full
    points = _checkpoints(len(df), n_checks, start)
    mismatches: list[dict[str, Any]] = []
    for t in points:
        head = call_signal_fn(fn, df.iloc[: int(t) + 1].reset_index(drop=True))
        if int(head[-1]) != int(sig[t]):
            mismatches.append({"bar": int(t), "full": int(sig[t]), "truncated": int(head[-1])})
    return {
        "status": _status(mismatches, int(points.size)),
        "checkpoints": int(points.size),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:MAX_REPORTED],
        "first_mismatch_bar": mismatches[0]["bar"] if mismatches else None,
    }


def mirror_future(df: pd.DataFrame, t: int) -> pd.DataFrame:
    """Copy of ``df`` whose bars after ``t`` follow mirrored log returns."""
    out = df.copy()
    close = out["close"].to_numpy(dtype=np.float64)
    if t + 1 >= close.size:
        return out
    log_ret = np.diff(np.log(close[t:]))
    factor = np.exp(-2.0 * np.cumsum(log_ret))
    for col in OHLC_COLS:
        vals = out[col].to_numpy(dtype=np.float64, copy=True)
        vals[t + 1 :] *= factor
        out[col] = vals
    return out


def probe_perturbation(
    fn: SignalFn,
    df: pd.DataFrame,
    *,
    n_checks: int = 6,
    start: int | None = None,
    full: np.ndarray | None = None,
) -> dict[str, Any]:
    """Rewrite the future after ``t``; the past signals must stay identical."""
    sig = call_signal_fn(fn, df) if full is None else full
    points = _checkpoints(len(df), n_checks, start)
    mismatches: list[dict[str, Any]] = []
    for t in points:
        alt = call_signal_fn(fn, mirror_future(df, int(t)))
        diff = np.flatnonzero(alt[: int(t) + 1] != sig[: int(t) + 1])
        if diff.size:
            mismatches.append({"checkpoint": int(t), "first_changed_bar": int(diff[0]), "changed_bars": int(diff.size)})
    return {
        "status": _status(mismatches, int(points.size)),
        "checkpoints": int(points.size),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:MAX_REPORTED],
    }


def _hit_rate(pos: np.ndarray, move: np.ndarray) -> tuple[float, int]:
    mask = (pos != 0) & (move != 0)
    n = int(np.count_nonzero(mask))
    if n == 0:
        return 0.5, 0
    return float(np.mean(np.sign(pos[mask]) == np.sign(move[mask]))), n


def implausible_accuracy(
    open_: np.ndarray,
    close: np.ndarray,
    signals: np.ndarray,
    *,
    max_hit_rate: float = 0.6,
    min_active: int = 100,
) -> dict[str, Any]:
    """Next-bar direction hit rate of active signals (leakage smell test)."""
    o = np.asarray(open_, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    s = np.asarray(signals, dtype=np.int64)
    if s.size < 3:
        return {"status": "skip", "hit_rate": None, "active_bars": 0}
    pos = s[:-1]
    rate_cc, n_cc = _hit_rate(pos, c[1:] - c[:-1])
    rate_oc, n_oc = _hit_rate(pos, c[1:] - o[1:])
    rate, n = (rate_cc, n_cc) if rate_cc >= rate_oc else (rate_oc, n_oc)
    z = (rate - 0.5) * 2.0 * float(np.sqrt(n)) if n else 0.0
    if n < min_active:
        status = "skip"
    else:
        status = "fail" if rate >= max_hit_rate else "pass"
    return {
        "status": status,
        "hit_rate": rate,
        "hit_rate_close_to_close": rate_cc,
        "hit_rate_next_bar_body": rate_oc,
        "active_bars": n,
        "z_score": float(z),
        "max_hit_rate": float(max_hit_rate),
    }


__all__ = [
    "implausible_accuracy",
    "mirror_future",
    "probe_determinism",
    "probe_perturbation",
    "probe_truncation",
]
