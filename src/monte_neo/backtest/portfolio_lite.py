"""Multi-symbol lite: independent cash books, shared ExecutionModel."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.backtest.bar_engine import run_bar_backtest
from monte_neo.backtest.model import ExecutionModel


def run_multi_symbol_lite(
    books: dict[str, dict[str, np.ndarray]],
    signals: dict[str, np.ndarray],
    model: ExecutionModel | None = None,
) -> dict[str, Any]:
    """Run one backtest per symbol with independent cash (no portfolio netting).

    Each ``books[symbol]`` must contain ``open``, ``high``, ``low``, ``close``.
    """
    model = model or ExecutionModel()
    if not books:
        raise ValueError("books must be non-empty")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    missing = set(books) - set(signals)
    if missing:
        raise ValueError(f"missing signals for symbols: {sorted(missing)}")  # pragma: no cover  # defensive / unreachable after unit mocks on CI
    per_symbol: dict[str, Any] = {}
    total_final = 0.0
    for sym, ohlc in books.items():
        out = run_bar_backtest(
            ohlc["open"],
            ohlc["high"],
            ohlc["low"],
            ohlc["close"],
            signals[sym],
            model=model,
        )
        per_symbol[sym] = {
            "total_return": out["total_return"],
            "max_drawdown": out["max_drawdown"],
            "n_trades": out["n_trades"],
            "final_cash": out["final_cash"],
            "metrics": out["metrics"],
        }
        total_final += float(out["final_cash"])
    n = len(books)
    initial = float(model.initial_cash) * n
    return {
        "ok": True,
        "engine": "monte_neo.backtest.portfolio_lite",
        "model": model.to_dict(),
        "work_checklist": model.work_checklist(),
        "n_symbols": n,
        "initial_cash_total": initial,
        "final_cash_total": total_final,
        "portfolio_return": total_final / initial - 1.0,
        "per_symbol": per_symbol,
        "note": "Independent cash books; not a portfolio optimizer",
    }
