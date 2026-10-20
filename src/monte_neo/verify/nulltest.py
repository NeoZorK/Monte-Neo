"""Random-walk null test: run the unchanged strategy on assets that have no relationship at all.

A correct strategy earns nothing on independent random walks. One that is reliably profitable there has a defect in its
accounting or its data handling, whatever it does on real data. The test needs no knowledge of the defect: it catches
phantom mean reversion in pairs strategies and other mechanical edges that statistics on the return series cannot see.
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo._version import __version__
from monte_neo.verify.checks import check
from monte_neo.verify.phantom import random_walk
from monte_neo.verify.schema import DISCLAIMER, VERDICT_SCHEMA_ID, aggregate_verdict, to_jsonable
from monte_neo.verify.verdict import certificate_id

FAIL_POSITIVE_SHARE = 0.75
FAIL_MEDIAN_T = 1.0
WARN_POSITIVE_SHARE = 0.65
WARN_MEDIAN_T = 0.5
SCOPE_NOTE = (
    "The strategy was run on independent random walks of your length and volatility. This finds mechanical edges "
    "(accounting, data handling); a pass does not show that the strategy has a real edge."
)
NEXT_ACTIONS: dict[str, str] = {
    "edge_on_noise": (
        "The strategy earns on prices that have no structure, so the profit is manufactured by the code. For a spread with a "
        "re-estimated hedge ratio, book the P&L from the legs (position.shift(1) * (d_y - beta.shift(1) * d_x)), then run "
        "verify --legs on the exported leg positions."
    ),
}


def load_pairs_strategy(spec: str) -> Callable[[pd.DataFrame], Any]:
    """Load ``path.py[:func]`` (default function ``pnl``): ``func(prices) -> per-bar returns``.

    ``prices`` is a DataFrame with one column ``leg1``, ``leg2``, ... of positive prices per leg. The function returns the
    per-bar return the strategy would report (a numpy array or a Series). The file is imported and executed: it is your own
    strategy code, with the same trust as ``--strategy``.
    """
    path, _, func = spec.partition(":")
    file = Path(path)
    if not file.is_file():
        raise ValueError(f"strategy file not found: {path}")
    mod_spec = importlib.util.spec_from_file_location(f"_mn_null_{file.stem}", file)
    if mod_spec is None or mod_spec.loader is None:
        raise ValueError(f"cannot import {path}")
    module = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(module)
    fn = getattr(module, func or "pnl", None)
    if not callable(fn):
        raise ValueError(f"{path} has no function {func or 'pnl'}(prices)")
    return fn  # type: ignore[no-any-return]


def _path_stats(returns: np.ndarray, ppy: float) -> tuple[float, float]:
    """``(annualized Sharpe, t-statistic of the mean)`` of one path; zeros when the strategy never traded."""
    r = returns[np.isfinite(returns)]
    sd = float(r.std(ddof=1)) if r.size > 1 else 0.0
    if sd <= 0.0:
        return 0.0, 0.0
    return float(r.mean() / sd * math.sqrt(ppy)), float(r.mean() / sd * math.sqrt(r.size))


def null_test(
    strategy: str | Callable[[pd.DataFrame], Any], *, n_paths: int = 100, bars: int = 3000, vol: float = 0.01,
    seed: int = 7, legs: int = 2, periods_per_year: float = 252.0,
) -> dict[str, Any]:
    """Run ``strategy`` on ``n_paths`` sets of ``legs`` independent random walks and judge the Sharpe ratios.

    Args:
        strategy: A ``path.py[:func]`` spec or a callable ``f(prices DataFrame) -> per-bar returns``.
        n_paths: Number of independent sets of walks (default 100).
        bars: Length of each walk; use the length of the real backtest.
        vol: Per-bar standard deviation of the log price; use the real one.
        seed: Seed of the walks.
        legs: Number of assets the strategy trades (columns ``leg1`` ... ``legN``).
        periods_per_year: Only for the annualized Sharpe printed in the report; the verdict uses t-statistics.

    Returns:
        A ``strategy-verdict/1`` report. Check ``edge_on_noise`` (economics) fails when more than 75% of the paths are
        profitable and the median t-statistic exceeds 1; it warns from 65% / 0.5. Under no edge the median t-statistic is
        about 0 with a standard error near 0.13 for 100 paths, so both limits are many standard errors away.
    """
    if n_paths < 20 or bars < 100 or legs < 1:
        raise ValueError("the null test needs at least 20 paths, 100 bars and 1 leg")
    fn = load_pairs_strategy(strategy) if isinstance(strategy, str) else strategy
    rng = np.random.default_rng(seed)
    sharpes, ts = [], []
    for _ in range(n_paths):
        prices = pd.DataFrame({f"leg{i + 1}": 100.0 * np.exp(random_walk(bars, vol, rng)) for i in range(legs)})
        out = np.asarray(fn(prices), dtype=np.float64)
        if out.ndim != 1 or out.size < 2:
            raise ValueError("the strategy must return one return per bar (a 1-D array or Series)")
        s, t = _path_stats(np.nan_to_num(out), periods_per_year)
        sharpes.append(s)
        ts.append(t)
    sr, t_arr = np.asarray(sharpes), np.asarray(ts)
    pos_share, med_sr, med_t = float((sr > 0).mean()), float(np.median(sr)), float(np.median(t_arr))
    details = {
        "paths": n_paths, "bars": bars, "vol": vol, "legs": legs, "seed": seed, "periods_per_year": periods_per_year,
        "median_sharpe": med_sr, "p05_sharpe": float(np.percentile(sr, 5)), "p95_sharpe": float(np.percentile(sr, 95)),
        "positive_share": pos_share, "median_t_stat": med_t,
    }
    text = f"on {n_paths} independent random-walk sets: median Sharpe {med_sr:+.2f}, {pos_share:.0%} positive, median t-statistic {med_t:+.2f}"
    if pos_share > FAIL_POSITIVE_SHARE and med_t > FAIL_MEDIAN_T:
        row = check("edge_on_noise", "economics", "fail", f"the strategy is profitable on pure noise, {text}.", details)
    elif pos_share >= WARN_POSITIVE_SHARE or med_t >= WARN_MEDIAN_T:
        row = check("edge_on_noise", "economics", "warn", f"the strategy leans profitable on pure noise, {text}.", details)
    else:
        row = check("edge_on_noise", "economics", "pass", f"no edge on noise, {text}.", details)
    checks = [check("null_test_scope", "integrity", "info", SCOPE_NOTE), row]
    verdict = aggregate_verdict(checks)
    name = strategy if isinstance(strategy, str) else getattr(strategy, "__name__", "callable")
    repro = {
        "engine": "monte-neo", "engine_version": __version__, "n_trials": 1,
        "data_sha256": hashlib.sha256(f"{name}|{n_paths}|{bars}|{vol}|{seed}|{legs}".encode()).hexdigest(),
        "settings": {"kind": "null_test", "strategy": name, "paths": n_paths, "bars": bars, "vol": vol, "seed": seed, "legs": legs},
    }
    problems = [c for c in checks if c["status"] in ("fail", "warn")]
    return to_jsonable({
        "schema": VERDICT_SCHEMA_ID, "verdict": verdict, "certificate_id": certificate_id(repro, verdict),
        "reasons": [f"{c['id']}: {c['summary']}" for c in problems], "checks": checks,
        "metrics": {k: details[k] for k in ("paths", "bars", "median_sharpe", "positive_share", "median_t_stat")},
        "next_actions": [NEXT_ACTIONS[c["id"]] for c in checks if c["id"] in NEXT_ACTIONS and c["status"] in ("fail", "warn")],
        "reproducibility": repro, "scope": SCOPE_NOTE,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "disclaimer": DISCLAIMER,
    })


__all__ = ["NEXT_ACTIONS", "SCOPE_NOTE", "load_pairs_strategy", "null_test"]
