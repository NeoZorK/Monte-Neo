"""Fee-aware engine for target weights over one or many instruments.

``weights[t, s]`` is the target fraction of equity in instrument ``s`` decided on
bar ``t`` (``+0.5`` = long half the equity, ``-1`` = short all of it). It is filled
at the open of bar ``t + 1`` when it differs from the last executed target, so a
weight that stays the same does not trade (positions drift with prices).

The accounting mirrors :func:`monte_neo.backtest.core_numba.run_core_full`: with
weights in ``{-1, 0, 1}`` on one instrument both engines give the same equity to
the last bit. A change of sign is two fills (close, then open from flat), exactly
as the discrete engine does it.

Missing prices are ``NaN``. An instrument cannot trade on a bar without a price;
the order waits for the next bar that has one. A position still open after the
instrument's last price (a delisting) is closed at that last price.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numba import njit

from monte_neo.backtest.model import ExecutionModel

__all__ = ["normalize_weights", "run_weight_backtest"]


@njit(cache=True)
def _weight_core(  # pragma: no cover  # njit body; covered through run_weight_backtest
    open_: np.ndarray,
    close: np.ndarray,
    weights: np.ndarray,
    last_bar: np.ndarray,
    fill_open: bool,
    commission_bps: float,
    slip_bps: float,
    initial_cash: float,
    warmup: int,
    funding_bps: float,
) -> tuple:
    n, m = close.shape
    equity = np.empty(n, dtype=np.float64)
    qty = np.zeros(m, dtype=np.float64)
    applied = np.zeros(m, dtype=np.float64)  # last executed target weight
    last_px = np.full(m, np.nan)
    cash = initial_cash
    peak_eq = initial_cash
    max_dd = 0.0
    fills = 0
    closed = 0
    traded_notional = 0.0
    fee_rate = commission_bps * 1e-4
    slip_rate = slip_bps * 1e-4
    fund_rate = funding_bps * 1e-4

    for i in range(n):
        # A position left open after the instrument's last price is closed at that price.
        for s in range(m):
            if qty[s] != 0.0 and i > last_bar[s]:
                side = 1.0 if qty[s] > 0.0 else -1.0
                px = last_px[s] * (1.0 - side * slip_rate)
                proceeds = qty[s] * px
                cash += proceeds - abs(proceeds) * fee_rate
                traded_notional += abs(proceeds)
                qty[s] = 0.0
                applied[s] = 0.0
                fills += 1
                closed += 1
        for s in range(m):
            if not np.isnan(close[i, s]):
                last_px[s] = close[i, s]
        if fund_rate > 0.0:
            for s in range(m):
                if qty[s] != 0.0 and not np.isnan(last_px[s]):
                    cash -= abs(qty[s] * last_px[s]) * fund_rate
        mtm = cash
        for s in range(m):
            if qty[s] != 0.0:
                mtm += qty[s] * last_px[s]
        equity[i] = mtm
        if mtm > peak_eq:
            peak_eq = mtm
        dd = (peak_eq - mtm) / peak_eq if peak_eq > 0.0 else 0.0
        if dd > max_dd:
            max_dd = dd

        if i < warmup or i + 1 >= n:
            continue
        for s in range(m):
            target = weights[i, s]
            if target == applied[s]:
                continue
            fill = open_[i + 1, s] if fill_open else close[i + 1, s]
            if np.isnan(fill) or fill <= 0.0:
                continue  # not tradable on this bar: the order waits
            # Close leg: a flat target or a change of side closes the whole position first.
            if qty[s] != 0.0 and (target == 0.0 or (target > 0.0) != (qty[s] > 0.0)):
                side = 1.0 if qty[s] > 0.0 else -1.0
                px = fill * (1.0 - side * slip_rate)
                proceeds = qty[s] * px
                cash += proceeds - abs(proceeds) * fee_rate
                traded_notional += abs(proceeds)
                qty[s] = 0.0
                fills += 1
                closed += 1
            if target != 0.0:
                base = cash + qty[s] * fill
                for k in range(m):
                    if k != s and qty[k] != 0.0:
                        base += qty[k] * last_px[k]
                if base <= 0.0:
                    continue  # nothing left to invest; retried like the discrete engine
                direction = 1.0 if target * base / fill > qty[s] else -1.0
                px = fill * (1.0 + direction * slip_rate)
                desired = target * base / px
                dq = desired - qty[s]
                if dq != 0.0:
                    cash -= dq * px + abs(dq * px) * fee_rate
                    traded_notional += abs(dq * px)
                    qty[s] = desired
                    fills += 1
                    if np.isnan(last_px[s]):
                        # First trade of a newly listed instrument: its fill is the only price known,
                        # and the next orders in this loop value the position with it.
                        last_px[s] = fill
            applied[s] = target

    for s in range(m):
        if qty[s] != 0.0:
            side = 1.0 if qty[s] > 0.0 else -1.0
            px = last_px[s] * (1.0 - side * slip_rate)
            proceeds = qty[s] * px
            cash += proceeds - abs(proceeds) * fee_rate
            traded_notional += abs(proceeds)
            qty[s] = 0.0
            fills += 1
            closed += 1
    if n > 0:
        equity[n - 1] = cash
    return equity, cash / initial_cash - 1.0, max_dd, fills, closed, traded_notional


def normalize_weights(weights: Any, *, long_short: bool = True, gross_limit: float = 1.0) -> tuple[np.ndarray, int]:
    """Clean target weights: NaN -> 0, clip to [-1, 1], cap gross exposure per bar.

    Returns ``(weights, scaled_bars)``; ``scaled_bars`` counts bars whose summed
    absolute weight exceeded ``gross_limit`` and was scaled down to it.
    """
    w = np.asarray(weights, dtype=np.float64)
    w = np.clip(np.nan_to_num(w, nan=0.0, posinf=1.0, neginf=-1.0), -1.0, 1.0)
    if not long_short:
        w = np.maximum(w, 0.0)
    if w.ndim == 1:
        return np.ascontiguousarray(w), 0
    gross = np.abs(w).sum(axis=1)
    over = gross > gross_limit
    if over.any():
        w = w.copy()
        w[over] *= (gross_limit / gross[over])[:, None]
    return np.ascontiguousarray(w), int(np.count_nonzero(over))


def run_weight_backtest(
    open_: np.ndarray,
    close: np.ndarray,
    weights: np.ndarray,
    model: ExecutionModel | None = None,
) -> dict[str, Any]:
    """Run target weights (1-D for one instrument, 2-D ``bars x instruments``).

    Weights are used as given (call :func:`normalize_weights` first); the model's
    ``size_fraction``, ``fill_fraction`` and ``leverage`` scale them like the
    discrete engine scales its notional. Stops (``sl_pct`` / ``tp_pct`` /
    ``trail_pct``) are not supported for weights.
    """
    model = model or ExecutionModel()
    if model.sl_pct > 0.0 or model.tp_pct > 0.0 or model.trail_pct > 0.0:
        raise ValueError("stop-loss / take-profit / trailing stops are not supported for target weights")
    o = np.asarray(open_, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    single = c.ndim == 1
    if single:
        o, c, w = o[:, None], c[:, None], w[:, None]
    if not (o.shape == c.shape == w.shape) or c.ndim != 2:
        raise ValueError("open, close and weights must share the shape (bars,) or (bars, instruments)")
    n = c.shape[0]
    if n < model.warmup_bars + 2:
        raise ValueError("need enough bars for warmup + fill")
    scale = float(model.size_fraction) * float(model.fill_fraction) * float(model.leverage)
    if model.side_mode != "long_short":
        w = np.maximum(w, 0.0)
    w = np.ascontiguousarray(w * scale)
    valid = ~np.isnan(c)
    has_price = valid.any(axis=0)
    last_bar = np.where(has_price, n - 1 - np.argmax(valid[::-1], axis=0), -1).astype(np.int64)
    equity, total_return, max_dd, fills, closed, traded = _weight_core(
        np.ascontiguousarray(o), np.ascontiguousarray(c), w, last_bar,
        model.fill_policy == "next_bar_open", float(model.commission_bps), float(model.effective_slip_bps),
        float(model.initial_cash), int(model.warmup_bars), float(model.funding_bps_per_bar),
    )
    return {
        "equity": equity,
        "total_return": float(total_return),
        "max_drawdown": float(max_dd),
        "n_trades": int(fills),
        "n_closed_trades": int(closed),
        "turnover": float(traded / float(model.initial_cash)),
    }
