"""``verify_grid`` — the verifier runs the parameter search itself.

Agents under-report how many variants they tried. Here the verifier expands
the grid, so ``n_trials`` and the spread of trial Sharpes are measured, not
declared. An anchored walk-forward re-selects parameters on past folds only and
scores them on the next fold, giving an out-of-sample Sharpe for the *process*.
"""

from __future__ import annotations

import itertools
import json
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel
from monte_neo.verify.checks import check
from monte_neo.verify.engine import simulate
from monte_neo.verify.ingest import (
    SignalFn,
    load_ohlcv,
    load_signal_fn,
    resolve_positions,
)
from monte_neo.verify.io_guard import IOWatch
from monte_neo.verify.market import SingleMarket, UniverseMarket, market_for
from monte_neo.verify.stats import bar_returns, sharpe_per_bar
from monte_neo.verify.verdict import _default_model, verify_strategy

MAX_COMBOS = 512
TOP_K = 5
# Neighbours of the best combo must keep at least this share of its Sharpe (median).
PLATEAU_MIN_RATIO = 0.5


def expand_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Cartesian product of ``{name: [values]}`` as a list of param dicts."""
    if not grid:
        raise ValueError("grid must name at least one parameter")
    names = sorted(grid)
    values = [list(grid[k]) for k in names]
    if any(not v for v in values):
        raise ValueError("every grid parameter needs at least one value")
    combos = [dict(zip(names, combo, strict=True)) for combo in itertools.product(*values)]
    if len(combos) > MAX_COMBOS:
        raise ValueError(f"grid has {len(combos)} combos (max {MAX_COMBOS})")
    return combos


def _trial_returns(
    fn: SignalFn, market: SingleMarket | UniverseMarket, combos: list[dict[str, Any]], model: ExecutionModel, positions: str
) -> tuple[np.ndarray, str]:
    """Per-bar returns of every combo, read with one positions mode for the whole grid."""
    values = []
    for params in combos:
        try:
            values.append(market.read_values(partial(fn, **params), None))
        except ValueError as exc:
            raise ValueError(f"{exc} for {params}") from exc
    mode = resolve_positions(np.concatenate(values), positions)
    rows = [
        bar_returns(simulate(market.ohlc, market.positions(v, mode, model)[0], model)["equity"], start=model.warmup_bars)
        for v in values
    ]
    return np.vstack(rows), mode


def walk_forward(returns: np.ndarray, folds: int = 4) -> dict[str, Any]:
    """Anchored walk-forward over a (combos x bars) per-bar return matrix."""
    n_bars = returns.shape[1]
    edges = np.linspace(0, n_bars, folds + 2).astype(int)
    chosen: list[int] = []
    oos: list[np.ndarray] = []
    for k in range(1, folds + 1):
        train = returns[:, : edges[k]]
        test = returns[:, edges[k] : edges[k + 1]]
        pick = int(np.argmax([sharpe_per_bar(r) for r in train]))
        chosen.append(pick)
        oos.append(test[pick])
    oos_rets = np.concatenate(oos) if oos else np.zeros(0)
    final = int(np.argmax([sharpe_per_bar(r) for r in returns]))
    return {
        "folds": int(folds),
        "chosen_combo_per_fold": chosen,
        "oos_bars": int(oos_rets.size),
        "oos_sharpe": sharpe_per_bar(oos_rets),
        "oos_total_return": float(np.prod(1.0 + oos_rets) - 1.0),
        "param_stability": float(np.mean(np.asarray(chosen) == final)) if chosen else 0.0,
    }


def _key(combo: dict[str, Any]) -> str:
    # JSON, not a tuple: grid values may be lists, which are not hashable.
    return json.dumps(combo, sort_keys=True, default=str)


def plateau(grid: dict[str, list[Any]], combos: list[dict[str, Any]], sharpes: np.ndarray, best: int) -> dict[str, Any]:
    """Sharpe of the best combo's neighbours: one parameter moved one step in the grid."""
    index = {_key(c): i for i, c in enumerate(combos)}
    neighbours: list[int] = []
    for name, values in grid.items():
        values = list(values)
        pos = values.index(combos[best][name])
        for step in (-1, 1):
            if 0 <= pos + step < len(values):
                moved = {**combos[best], name: values[pos + step]}
                neighbours.append(index[_key(moved)])
    best_sharpe = float(sharpes[best])
    near = [float(sharpes[i]) for i in neighbours]
    ratio = float(np.median(near)) / best_sharpe if near and best_sharpe > 0.0 else None
    return {"best_sharpe_per_bar": best_sharpe, "neighbour_sharpes": near, "median_ratio": ratio}


def plateau_row(info: dict[str, Any]) -> dict[str, Any]:
    """Statistics check: is the best combo on a plateau or an isolated peak?"""
    ratio = info["median_ratio"]
    if ratio is None:
        reason = "no neighbouring combos" if not info["neighbour_sharpes"] else "best combo is not profitable"
        return check("parameter_plateau", "statistics", "skip", f"parameter plateau: {reason}", info)
    status = "pass" if ratio >= PLATEAU_MIN_RATIO else "warn"
    summary = f"neighbouring parameters keep {ratio:.0%} of the best Sharpe (median of {len(info['neighbour_sharpes'])})"
    return check("parameter_plateau", "statistics", status, summary, info)


def walk_forward_row(wf: dict[str, Any], in_sample_sharpe: float) -> dict[str, Any]:
    """Statistics check: does re-selecting on the past keep working on the next fold?"""
    oos = float(wf["oos_sharpe"])
    if oos <= 0.0:
        status = "fail"
    elif in_sample_sharpe > 0.0 and oos < 0.5 * in_sample_sharpe:
        status = "warn"
    else:
        status = "pass"
    summary = f"walk-forward OOS Sharpe/bar {oos:+.4f} vs in-sample best {in_sample_sharpe:+.4f}"
    return check("walk_forward_oos", "statistics", status, summary, wf)


def verify_grid(
    ohlcv: pd.DataFrame | str | Path,
    grid: dict[str, list[Any]],
    *,
    strategy: str | Path | None = None,
    signal_fn: SignalFn | None = None,
    source: str | None = None,
    model: ExecutionModel | None = None,
    folds: int = 4,
    **verify_kwargs: Any,
) -> dict[str, Any]:
    """Search ``grid`` over ``signal(df, **params)``, then verify the best combo.

    The verdict prices selection with the measured ``n_trials`` and trial
    Sharpe spread and adds a ``walk_forward_oos`` check.
    """
    if int(folds) < 1:
        raise ValueError(f"folds must be >= 1, got {folds}")
    df = load_ohlcv(ohlcv)
    io_watch = IOWatch(tuple(p for p in (df.attrs.get("source_path"),) if p))
    with io_watch:
        if strategy is not None:
            signal_fn, text = load_signal_fn(strategy)
            source = source if source is not None else text
    if signal_fn is None:
        raise ValueError("verify_grid needs strategy= or signal_fn=")
    market = market_for(df)
    model = model or _default_model(market.n_bars)
    combos = expand_grid(grid)
    positions = verify_kwargs.pop("positions", "auto")
    with io_watch:
        returns, mode = _trial_returns(signal_fn, market, combos, model, positions)
    sharpes = np.array([sharpe_per_bar(r) for r in returns])
    order = np.argsort(-sharpes)
    best = combos[int(order[0])]
    wf = walk_forward(returns, folds=folds)
    peak = plateau(grid, combos, sharpes, int(order[0]))
    section = {
        "grid": {
            "spec": {k: list(v) for k, v in grid.items()},
            "folds": int(folds),
            "n_combos": len(combos),
            "best_params": best,
            "top": [{"params": combos[int(i)], "sharpe_per_bar": float(sharpes[i])} for i in order[:TOP_K]],
            "walk_forward": wf,
            "plateau": peak,
        }
    }
    return verify_strategy(
        df,
        signal_fn=partial(signal_fn, **best),
        source=source,
        model=model,
        n_trials=len(combos),
        trial_sharpes=sharpes if len(combos) >= 2 else None,
        extra_checks=[walk_forward_row(wf, float(sharpes[order[0]])), plateau_row(peak)],
        extra=section,
        io_watch=io_watch,
        positions=mode,
        **verify_kwargs,
    )


__all__ = ["MAX_COMBOS", "expand_grid", "plateau", "plateau_row", "verify_grid", "walk_forward", "walk_forward_row"]
