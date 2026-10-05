"""Per-bar returns of a strategy on a table, through the same engine the verifier uses."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.engine import simulate
from monte_neo.verify.ingest import load_signal_fn, resolve_positions
from monte_neo.verify.market import market_for
from monte_neo.verify.stats import bar_returns, infer_periods_per_year


def strategy_returns(
    df: pd.DataFrame, strategy: str | Path | Callable[..., Any], model: ExecutionModel | None = None
) -> tuple[np.ndarray, float, str | None]:
    """``(returns after costs, periods per year, source)`` of ``strategy`` (a file spec or a callable) on ``df``."""
    from monte_neo.verify.verdict import _default_model

    market = market_for(df)
    source = None
    if callable(strategy):
        fn = strategy
    else:
        fn, source = load_signal_fn(strategy)
    model = model or _default_model(market.n_bars)
    values = market.read_values(fn, None)
    mode = resolve_positions(values, "auto")
    sig, _ = market.positions(values, mode, model)
    run = simulate(market.ohlc, sig, model)
    rets = bar_returns(run["equity"], start=model.warmup_bars)
    return rets, float(infer_periods_per_year(market.timestamps)), source


def annualized_sharpe(rets: np.ndarray, periods_per_year: float) -> float:
    r = np.asarray(rets, dtype=np.float64)
    if r.size < 2 or not np.isfinite(r).all():
        return 0.0
    sd = float(r.std(ddof=1))
    return 0.0 if sd == 0.0 else float(r.mean() / sd * np.sqrt(periods_per_year))


__all__ = ["annualized_sharpe", "strategy_returns"]
