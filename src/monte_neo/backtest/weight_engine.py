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

from monte_neo.backtest.core_numba import _stop_hit
from monte_neo.backtest.jit import njit_cached
from monte_neo.backtest.model import ExecutionModel

__all__ = ["normalize_weights", "run_weight_backtest"]


@njit_cached
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
    borrow_bps: float,
    high: np.ndarray,
    low: np.ndarray,
    sl_pct: float,
    tp_pct: float,
    trail_pct: float,
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
    borrow_rate = borrow_bps * 1e-4
    use_sl = sl_pct > 0.0
    use_tp = tp_pct > 0.0
    use_trail = trail_pct > 0.0
    use_stops = use_sl or use_tp or use_trail
    sl_lvl = np.zeros(m, dtype=np.float64)  # stop, take-profit and trailing-peak levels of each open position
    tp_lvl = np.zeros(m, dtype=np.float64)
    peak_lvl = np.zeros(m, dtype=np.float64)

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
        if borrow_rate > 0.0:
            for s in range(m):
                if qty[s] < 0.0 and not np.isnan(last_px[s]):
                    cash -= abs(qty[s] * last_px[s]) * borrow_rate
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

        if use_stops:
            # Stops inside the bar, exactly as the discrete engine does them: a position that touches
            # its level on this bar leaves at that level (slippage against it) and the target is free
            # to re-enter from the next decision.
            stopped = False
            for s in range(m):
                if qty[s] != 0.0 and not np.isnan(high[i, s]) and not np.isnan(low[i, s]):
                    pos = 1 if qty[s] > 0.0 else -1
                    hit, exit_raw, sl_lvl[s], peak_lvl[s] = _stop_hit(
                        pos, high[i, s], low[i, s], use_sl, use_tp, use_trail,
                        sl_lvl[s], tp_lvl[s], peak_lvl[s], trail_pct,
                    )
                    if hit != 0:
                        px = exit_raw * (1.0 - float(pos) * slip_rate)
                        proceeds = qty[s] * px
                        cash += proceeds - abs(proceeds) * fee_rate
                        traded_notional += abs(proceeds)
                        qty[s] = 0.0
                        applied[s] = 0.0
                        fills += 1
                        closed += 1
                        stopped = True
            if stopped:
                after = cash
                for s in range(m):
                    if qty[s] != 0.0:
                        after += qty[s] * last_px[s]
                equity[i] = after

        if i < warmup or i + 1 >= n:
            continue
        # Value of all open positions, kept up to date as orders fill below, so sizing an
        # order costs O(1) instead of a loop over every instrument (O(instruments^2) per bar).
        hold = 0.0
        for s in range(m):
            if qty[s] != 0.0:
                hold += qty[s] * last_px[s]
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
                hold -= qty[s] * last_px[s]
                qty[s] = 0.0
                fills += 1
                closed += 1
            if target != 0.0:
                held = qty[s] * last_px[s] if qty[s] != 0.0 else 0.0
                base = cash + (hold - held) + qty[s] * fill
                if base <= 0.0:
                    continue  # nothing left to invest; retried like the discrete engine
                direction = 1.0 if target * base / fill > qty[s] else -1.0
                px = fill * (1.0 + direction * slip_rate)
                desired = target * base / px
                dq = desired - qty[s]
                if dq != 0.0:
                    cash -= dq * px + abs(dq * px) * fee_rate
                    traded_notional += abs(dq * px)
                    if np.isnan(last_px[s]):
                        # First trade of a newly listed instrument: its fill is the only price known,
                        # and the next orders in this loop value the position with it.
                        last_px[s] = fill
                    hold += (desired - qty[s]) * last_px[s]
                    opening = qty[s] == 0.0
                    qty[s] = desired
                    fills += 1
                    if use_stops and opening:
                        # Levels come from the price a position is opened at; adding to it or
                        # trimming it later keeps them.
                        peak_lvl[s] = px
                        if use_sl:
                            sl_lvl[s] = px * (1.0 - sl_pct * 0.01) if desired > 0.0 else px * (1.0 + sl_pct * 0.01)
                        elif use_trail:
                            sl_lvl[s] = px * (1.0 - trail_pct * 0.01) if desired > 0.0 else px * (1.0 + trail_pct * 0.01)
                        if use_tp:
                            tp_lvl[s] = px * (1.0 + tp_pct * 0.01) if desired > 0.0 else px * (1.0 - tp_pct * 0.01)
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
    high: np.ndarray | None = None,
    low: np.ndarray | None = None,
) -> dict[str, Any]:
    """Run target weights (1-D for one instrument, 2-D ``bars x instruments``).

    Weights are used as given (call :func:`normalize_weights` first); the model's
    ``size_fraction``, ``fill_fraction`` and ``leverage`` scale them like the
    discrete engine scales its notional.

    Stops (``sl_pct`` / ``tp_pct`` / ``trail_pct``, in percent) work inside the bar and need
    ``high`` and ``low`` of the same shape as ``close``. They follow the discrete engine: the
    levels come from the price a position is opened at (from flat, or after a change of side),
    the stop is tested before the take-profit when a bar touches both, and the position leaves at
    the level with slippage against it. Adding to a position or trimming it keeps its levels.
    A stopped instrument is flat until the target asks for a position again, which it may do on
    the same bar (the target has not changed, so a held weight re-enters at the next open).
    """
    model = model or ExecutionModel()
    stops = model.sl_pct > 0.0 or model.tp_pct > 0.0 or model.trail_pct > 0.0
    o = np.asarray(open_, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    hi = None if high is None else np.asarray(high, dtype=np.float64)
    lo = None if low is None else np.asarray(low, dtype=np.float64)
    if stops and (hi is None or lo is None):
        raise ValueError("stop-loss / take-profit / trailing stops need the bars' high and low")
    single = c.ndim == 1
    if single:
        o, c, w = o[:, None], c[:, None], w[:, None]
        hi = None if hi is None else hi[:, None]
        lo = None if lo is None else lo[:, None]
    if not (o.shape == c.shape == w.shape) or c.ndim != 2:
        raise ValueError("open, close and weights must share the shape (bars,) or (bars, instruments)")
    if stops and not (hi.shape == lo.shape == c.shape):  # type: ignore[union-attr]
        raise ValueError("high and low must have the shape of close")
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
        float(model.initial_cash), int(model.warmup_bars), float(model.funding_bps_per_bar), float(model.borrow_bps_per_bar),
        np.ascontiguousarray(hi if stops else c), np.ascontiguousarray(lo if stops else c),  # placeholders when unused
        float(model.sl_pct), float(model.tp_pct), float(model.trail_pct),
    )
    return {
        "equity": equity,
        "total_return": float(total_return),
        "max_drawdown": float(max_dd),
        "n_trades": int(fills),
        "n_closed_trades": int(closed),
        "turnover": float(traded / float(model.initial_cash)),
    }
