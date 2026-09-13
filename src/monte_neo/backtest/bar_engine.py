"""Python API for the professional fee-aware bar engine."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.backtest.core_numba import run_core_full, run_terminal_return
from monte_neo.backtest.metrics import summarize_backtest
from monte_neo.backtest.model import ExecutionModel
from monte_neo.backtest.strategy import StrategySpec, build_signal
from monte_neo.backtest.trades import pack_trades

__all__ = ["run_bar_backtest", "run_strategy_backtest", "run_terminal_return"]


def _model_slip_bps(model: ExecutionModel) -> float:
    return float(model.effective_slip_bps)


def run_bar_backtest(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signal: np.ndarray,
    model: ExecutionModel | None = None,
) -> dict[str, Any]:
    """Run one bar backtest under a frozen :class:`ExecutionModel`."""
    model = model or ExecutionModel()
    o = np.asarray(open_, dtype=np.float64)
    h = np.asarray(high, dtype=np.float64)
    l = np.asarray(low, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    s = np.asarray(signal, dtype=np.int64)
    if not (o.shape == h.shape == l.shape == c.shape == s.shape):
        raise ValueError("OHLC and signal must share the same shape")
    if o.ndim != 1 or o.size < model.warmup_bars + 2:
        raise ValueError("need 1-D series with enough bars for warmup + fill")

    (
        equity,
        total_return,
        max_dd,
        fill_events,
        final_cash,
        n_closed,
        te_i,
        tx_i,
        te_px,
        tx_px,
        t_qty,
        t_fees,
        t_reason,
    ) = run_core_full(
        o,
        h,
        l,
        c,
        s,
        model.fill_policy == "next_bar_open",
        model.side_mode == "long_short",
        float(model.size_fraction),
        float(model.commission_bps),
        _model_slip_bps(model),
        float(model.initial_cash),
        int(model.warmup_bars),
        float(model.sl_pct),
        float(model.tp_pct),
        float(model.trail_pct),
        float(model.fill_fraction),
    )
    trades = pack_trades(
        n_closed, te_i, tx_i, te_px, tx_px, t_qty, t_fees, t_reason
    )
    metrics = summarize_backtest(
        equity, trades, initial_cash=model.initial_cash, max_drawdown=float(max_dd)
    )
    return {
        "ok": True,
        "engine": "monte_neo.backtest",
        "model": model.to_dict(),
        "work_checklist": model.work_checklist,
        "total_return": float(total_return),
        "max_drawdown": float(max_dd),
        "n_trades": int(fill_events),
        "n_closed_trades": int(n_closed),
        "final_cash": float(final_cash),
        "equity": equity,
        "trades": trades,
        "metrics": metrics,
    }


def run_strategy_backtest(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    spec: StrategySpec,
    model: ExecutionModel | None = None,
) -> dict[str, Any]:
    """Compile ``spec`` to signals and run the shared ExecutionModel path."""
    sig = build_signal(close, spec)
    out = run_bar_backtest(open_, high, low, close, sig, model=model)
    out["strategy"] = {"kind": spec.kind, "fast": spec.fast, "slow": spec.slow}
    return out
