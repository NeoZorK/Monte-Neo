"""Cross-market replication: new out-of-sample evidence today, from markets the search never used.

A rule found on one market and checked on years it was tuned on has no fresh data left; waiting for a forward record
takes months to show little. Markets that took no part in the search are fresh data now. This module runs the frozen
rule, unchanged, on every such market and asks two questions:

1. Per market: the full Monte-Neo verdict (``verify_strategy`` with the project's trials and costs).
2. Together: the equal-weight portfolio "this rule on every replication market", net of the same costs. Its t-statistic
   is reported with the effective number of independent markets (participation ratio of the correlation eigenvalues,
   :func:`monte_neo.research.breadth.effective_breadth`), so twenty coins that move together do not count as twenty tests.

Integrity: a market used in discovery or validation is refused (``discovery`` list), and the list of replication markets
should be written down before the run (pre-registration); the report records both lists and the data hashes.
Check row ``cross_market_replication``: pass when the portfolio t >= 2 and at least 60 % of markets are net positive;
fail when the portfolio t <= -2; warn otherwise.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check

T_PASS, SHARE_PASS = 2.0, 0.6


def _signal_fn(strategy: Path) -> Any:
    from monte_neo.verify.ingest import load_signal_fn

    return load_signal_fn(f"{strategy}:signal")[0]


def net_returns(df: pd.DataFrame, positions: np.ndarray, cost_bps: float) -> pd.Series:
    """Next-bar returns of the positions, minus ``cost_bps`` per unit of position change (the same model on every market)."""
    close = df["close"].astype(float).to_numpy()
    ret = np.zeros(len(close))
    ret[1:] = close[1:] / close[:-1] - 1.0
    pos = np.nan_to_num(np.asarray(positions, dtype=float))
    held = np.concatenate([[0.0], pos[:-1]])
    turnover = np.abs(np.diff(np.concatenate([[0.0], pos])))
    net = held * ret - turnover * cost_bps / 1e4
    idx = pd.to_datetime(df["timestamp"], utc=True) if "timestamp" in df else pd.RangeIndex(len(df))
    return pd.Series(net, index=idx)


def _tstat(r: pd.Series) -> tuple[float, float]:
    r = r.dropna()
    if len(r) < 30 or r.std() == 0:
        return float("nan"), float("nan")
    t = r.mean() / r.std() * math.sqrt(len(r))
    return float(t), float(r.mean() / r.std())


def replicate(strategy: str | Path, markets: dict[str, str | Path], *, discovery: list[str], n_trials: int,
              fee_bps: float = 10.0, slippage_bps: float = 5.0, periods_per_year: float = 365.0,
              run_verify: bool = True) -> dict[str, Any]:
    """Run the frozen rule on every replication market; returns per-market results, the pooled portfolio and a check row."""
    from monte_neo.research.breadth import effective_breadth
    from monte_neo.verify import load_ohlcv, model_from_costs, verify_strategy
    from monte_neo.verify.market import bar_count

    searched = {d.upper() for d in discovery}
    used = sorted(m for m in markets if m.upper() in searched)
    if used:
        raise ValueError(f"these markets took part in the search and are not out of sample: {', '.join(used)}")
    if len(markets) < 3:
        raise ValueError("replication needs at least 3 markets that took no part in the search")
    strategy = Path(strategy)
    fn = _signal_fn(strategy)
    per, series = [], {}
    cost = fee_bps + slippage_bps
    for name, path in sorted(markets.items()):
        df = load_ohlcv(path)
        r = net_returns(df, fn(df), cost)
        series[name] = r
        t, sr = _tstat(r)
        row: dict[str, Any] = {"market": name, "bars": len(df), "net_sharpe": None if math.isnan(sr) else sr * math.sqrt(periods_per_year),
                               "t": None if math.isnan(t) else t, "net_total_return": float((1 + r).prod() - 1),
                               "data_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
        if run_verify:
            model = model_from_costs(commission_bps=fee_bps, slippage_bps=slippage_bps, side_mode="long_flat", n_bars=bar_count(df))
            rep = verify_strategy(df, strategy=strategy, n_trials=n_trials, model=model)
            row.update(verdict=rep["verdict"], certificate_id=rep.get("certificate_id"), arl=(rep.get("arl") or {}).get("level"))
        per.append(row)
    panel = pd.DataFrame(series).sort_index().dropna(how="all").fillna(0.0)
    pooled = panel.mean(axis=1)
    t, sr = _tstat(pooled)
    breadth = effective_breadth(panel.to_numpy())
    share = sum(1 for p in per if p["net_total_return"] > 0) / len(per)
    status = "pass" if t >= T_PASS and share >= SHARE_PASS else ("fail" if t <= -T_PASS else "warn")
    details = {"markets": len(per), "effective_markets": round(float(breadth.get("n_eff") or 0), 1), "share_net_positive": share,
               "pooled_net_sharpe": None if math.isnan(sr) else sr * math.sqrt(periods_per_year), "pooled_t": t,
               "discovery_markets": sorted(discovery), "n_trials": n_trials, "cost_bps_per_change": cost}
    summary = (f"the frozen rule on {len(per)} markets outside the search ({details['effective_markets']} independent): "
               f"{share:.0%} net positive, pooled net Sharpe {details['pooled_net_sharpe']:.2f}, t {t:.2f}"
               if not math.isnan(t) else "too little data for a pooled test")
    return {"schema": "cross-market-replication/1", "markets": per, "pooled": details,
            "check": check("cross_market_replication", "statistics", status, summary, details),
            "disclaimer": "Replication on other markets is evidence about the rule, not a forecast. Not investment advice."}
