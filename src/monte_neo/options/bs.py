"""Black-Scholes-Merton price and gamma with a continuous dividend yield (European; a stress model, not a quote)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

_erf = np.frompyfunc(math.erf, 1, 1)


def _cdf(x: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + _erf(np.asarray(x, dtype=float) / math.sqrt(2.0)).astype(float))


def _pdf(x: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * np.square(x)) / math.sqrt(2.0 * math.pi)


def _d1d2(s: np.ndarray, k: np.ndarray, t: np.ndarray, vol: np.ndarray, r: float, q: float) -> tuple[np.ndarray, np.ndarray]:
    v = vol * np.sqrt(t)
    d1 = (np.log(s / k) + (r - q + 0.5 * vol**2) * t) / v
    return d1, d1 - v


def price(s: Any, k: Any, t: Any, vol: Any, is_call: Any, r: float = 0.0, q: float = 0.0) -> np.ndarray:
    """Option value per share. At or after expiry (``t <= 0``) or with zero volatility it is the intrinsic value."""
    s, k, t, vol = (np.atleast_1d(np.asarray(x, dtype=float)) for x in (s, k, t, vol))
    call = np.atleast_1d(np.asarray(is_call, dtype=bool))
    intrinsic = np.where(call, np.maximum(s - k, 0.0), np.maximum(k - s, 0.0))
    live = (t > 1e-9) & (vol > 1e-9)
    if not live.any():
        return intrinsic
    s_, k_, t_, v_, c_ = (np.broadcast_to(a, np.broadcast(s, k, t, vol, call).shape)[live] for a in (s, k, t, vol, call))
    d1, d2 = _d1d2(s_, k_, t_, v_, r, q)
    disc_s, disc_k = s_ * np.exp(-q * t_), k_ * np.exp(-r * t_)
    val = np.where(c_, disc_s * _cdf(d1) - disc_k * _cdf(d2), disc_k * _cdf(-d2) - disc_s * _cdf(-d1))
    out = np.array(np.broadcast_to(intrinsic, np.broadcast(s, k, t, vol, call).shape), dtype=float)
    out[live] = val
    return out


def gamma(s: Any, k: Any, t: Any, vol: Any, r: float = 0.0, q: float = 0.0) -> np.ndarray:
    """Gamma per share (same for calls and puts); zero at or after expiry."""
    s, k, t, vol = (np.atleast_1d(np.asarray(x, dtype=float)) for x in (s, k, t, vol))
    out = np.zeros(np.broadcast(s, k, t, vol).shape)
    live = np.broadcast_to((t > 1e-9) & (vol > 1e-9), out.shape)
    if live.any():
        s_, k_, t_, v_ = (np.broadcast_to(a, out.shape)[live] for a in (s, k, t, vol))
        d1, _ = _d1d2(s_, k_, t_, v_, r, q)
        out[live] = np.exp(-q * t_) * _pdf(d1) / (s_ * v_ * np.sqrt(t_))
    return out
