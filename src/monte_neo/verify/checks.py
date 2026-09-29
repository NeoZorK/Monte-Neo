"""Turn raw probe / engine outputs into ``strategy-verdict/1`` check rows."""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.backtest.model import ExecutionModel

# Fix-it hints an agent can act on, keyed by check id.
NEXT_ACTIONS: dict[str, str] = {
    "data_integrity": "Clean the OHLCV: sort bars oldest-first, drop duplicate timestamps, NaN rows, non-positive prices and broken bars (high < low, open or close outside high-low).",
    "determinism": "Make the signal deterministic: seed every RNG and avoid wall-clock or I/O inside signal().",
    "lookahead_truncation": "The signal at bar t changes when later bars are removed: compute features only from rows <= t (no shift(-k), centered windows, bfill or full-sample stats).",
    "lookahead_perturbation": "Past signals change when the future is rewritten: remove whole-series statistics (mean/std/min/max over all rows) and future-dependent fills.",
    "survivorship": "Build the universe point-in-time: include the symbols that were delisted or dropped during the test, or the backtest only trades survivors.",
    "external_data": "signal() must use only the df it is given: pass parameters as function defaults and do not load data from files or the network, which the look-ahead probes cannot see.",
    "lookahead_static_lint": "Fix the flagged source lines (negative shift, center=True, backward fill) and re-run verify.",
    "implausible_accuracy": "Next-bar hit rate is too high to be real: look for leakage of the next bar's close/open into the signal.",
    "costs_modeled": "Re-run with realistic costs (e.g. commission_bps=5, slippage_bps=5 for liquid crypto).",
    "net_profitability": "The strategy loses money after costs: reduce turnover or find a stronger edge.",
    "cost_margin": "Edge barely covers costs: cut turnover or test with higher slippage before trusting it.",
    "delay_sensitivity": "Profit disappears with one bar of execution delay: the edge lives in fill timing.",
    "timing_significance": "The profit comes from market exposure, not timing: shifted copies of the same positions earn as much. Compare with buy-and-hold at the same exposure, or find a signal that beats its own shifted copies.",
    "period_consistency": "The profit comes from one period: find out what happened there (a regime, an event, a data error) and test on more history.",
    "sample_size": "Too few closed trades for statistics: test on more history or more instruments.",
    "deflated_sharpe": "Sharpe does not survive the number of variants tried: test out-of-sample or reduce the search space.",
    "trials_disclosed": "Pass n_trials = number of variants you tried (parameters, rules, assets) so selection bias is priced in.",
    "holdout_consistency": "Recent (holdout) performance does not confirm the earlier sample: check for regime dependence or overfit.",
    "parameter_plateau": "The best parameters are an isolated peak: neighbouring values do much worse. Prefer a region where nearby parameters also work.",
    "walk_forward_oos": "Parameters picked on past folds do not hold on the next fold: shrink the grid or prefer robust parameter plateaus.",
}


def check(
    check_id: str, category: str, status: str, summary: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build one check row."""
    return {"id": check_id, "category": category, "status": status, "summary": summary, "details": details or {}}


def _time_order(timestamps: Any) -> tuple[int, int]:
    """Count backward steps and repeated stamps; unparseable stamps are ignored."""
    if timestamps is None:
        return 0, 0
    values = pd.Series(np.asarray(timestamps))
    if pd.api.types.is_numeric_dtype(values):
        ts = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=np.float64)
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(values, utc=True, errors="coerce").dropna()
        ts = parsed.to_numpy(dtype="datetime64[ns]").astype(np.int64)
    steps = np.diff(ts)
    return int(np.count_nonzero(steps < 0)), int(np.count_nonzero(steps == 0))


# Open or close outside [low, high] by more than this share of the price is a broken bar.
# Smaller gaps are vendor rounding: counted in the details, not failed.
OHLC_TOLERANCE = 1e-3


def data_integrity(ohlc: dict[str, np.ndarray], timestamps: Any = None, *, duplicates: int = 0) -> dict[str, Any]:
    """NaN, non-positive prices, inconsistent bars and bars out of time order.

    Rows must run oldest-first: on newest-first data ``shift(1)`` reads the next bar,
    a look-ahead the row-order probes cannot see.
    """
    o, h, l, c = (ohlc[k] for k in ("open", "high", "low", "close"))
    stacked = np.vstack([o, h, l, c])
    n_nan = int(np.count_nonzero(~np.isfinite(stacked)))
    n_nonpos = int(np.count_nonzero(np.nan_to_num(stacked, nan=1.0) <= 0.0))
    n_inverted = int(np.count_nonzero(np.nan_to_num(h) < np.nan_to_num(l)))
    with np.errstate(invalid="ignore"):
        above = np.fmax(o, c) - h  # open or close above the high
        below = l - np.fmin(o, c)  # open or close below the low
        gap = np.nan_to_num(np.fmax(above, below) / np.abs(c), nan=0.0)
    n_outside = int(np.count_nonzero(gap > OHLC_TOLERANCE))
    n_rounding = int(np.count_nonzero((gap > 0.0) & (gap <= OHLC_TOLERANCE)))
    n_backward, n_repeated = _time_order(timestamps)
    n_repeated += int(duplicates)  # a universe passes repeated (timestamp, symbol) rows here
    problems = [
        (n_nan, "NaN"),
        (n_nonpos, "non-positive"),
        (n_inverted, "high<low"),
        (n_outside, "open/close outside high-low"),
        (n_backward, "out-of-order timestamp"),
        (n_repeated, "duplicate timestamp"),
    ]
    found = [f"{count} {label}" for count, label in problems if count]
    summary = ", ".join(found) + " values" if found else "OHLCV is clean"
    return check(
        "data_integrity", "integrity", "fail" if found else "pass", summary,
        {
            "nan_values": n_nan,
            "non_positive_values": n_nonpos,
            "inverted_bars": n_inverted,
            "open_close_outside_range": n_outside,
            "rounding_outside_range": n_rounding,
            "out_of_order_timestamps": n_backward,
            "duplicate_timestamps": n_repeated,
        },
    )


def probe_row(check_id: str, probe: dict[str, Any] | None, what: str) -> dict[str, Any]:
    """Wrap a look-ahead probe (``None`` means it could not run)."""
    category = "integrity" if check_id == "determinism" else "lookahead"
    if probe is None:
        return check(check_id, category, "skip", f"{what}: needs strategy code (signal function)")
    status = probe["status"]
    summary = f"{what}: {'no leak detected' if status == 'pass' else 'LEAK DETECTED' if status == 'fail' else status}"
    if check_id == "determinism":
        summary = "signal() is not deterministic" if status == "fail" else "signal() is deterministic"
    return check(check_id, category, status, summary, probe)


def external_data_row(files: list[str] | None, connections: list[str] | None) -> dict[str, Any]:
    """Data the strategy read outside ``df`` (``None`` means no strategy code ran)."""
    if files is None or connections is None:
        return check("external_data", "lookahead", "skip", "outside data: needs strategy code (signal function)")
    if not files and not connections:
        return check("external_data", "lookahead", "pass", "outside data: none read (df only)")
    found = [*(f"file {name}" for name in files), *(f"network {host}" for host in connections)]
    return check(
        "external_data", "lookahead", "fail", "outside data: reads " + ", ".join(found),
        {"files": files, "connections": connections},
    )


def survivorship_row(symbols: list[str], first_bar: np.ndarray, last_bar: np.ndarray, n_bars: int) -> dict[str, Any]:
    """A universe where no symbol stops trading was probably picked from today's survivors."""
    dropped = [s for s, last in zip(symbols, last_bar, strict=True) if last < n_bars - 1]
    listed_late = int(np.count_nonzero(np.asarray(first_bar) > 0))
    details = {"symbols": len(symbols), "stopped_trading": dropped[:20], "stopped_count": len(dropped), "listed_late": listed_late}
    if len(symbols) < 2:
        return check("survivorship", "integrity", "skip", "survivorship: one symbol", details)
    if not dropped:
        summary = f"all {len(symbols)} symbols trade until the last bar: delisted names may be missing (survivorship bias)"
        return check("survivorship", "integrity", "warn", summary, details)
    return check(
        "survivorship", "integrity", "pass",
        f"{len(dropped)} of {len(symbols)} symbols stop trading before the end (delistings included)", details,
    )


def lint_row(lint: dict[str, Any] | None) -> dict[str, Any]:
    """Wrap static lint findings."""
    if lint is None:
        return check("lookahead_static_lint", "lookahead", "skip", "static lint: no source provided")
    rules = sorted({f["rule"] for f in lint["findings"]})
    if lint["status"] == "skip":
        summary = f"static lint: {lint.get('error', 'not run')}"
    else:
        summary = "static lint: clean" if not rules else f"static lint: {', '.join(rules)}"
    return check("lookahead_static_lint", "lookahead", lint["status"], summary, lint)


def accuracy_row(acc: dict[str, Any]) -> dict[str, Any]:
    """Wrap the implausible-accuracy smell test."""
    rate = acc.get("hit_rate")
    if acc["status"] == "skip":
        summary = "next-bar hit rate: too few active bars"
    else:
        summary = f"next-bar hit rate {rate:.3f} over {acc.get('active_bars', 0)} bars (z {acc.get('z_score', 0.0):.1f})"
    return check("implausible_accuracy", "lookahead", acc["status"], summary, acc)


def economics_rows(
    model: ExecutionModel, total_return: float, breakeven: dict[str, Any], delay: dict[str, Any]
) -> list[dict[str, Any]]:
    """Costs modeled, net profitability, cost margin and delay sensitivity."""
    side_cost = float(model.commission_bps + model.slippage_bps + model.impact_bps)
    rows = [
        check(
            "costs_modeled", "economics", "warn" if side_cost <= 0.0 else "pass",
            "no trading costs modeled" if side_cost <= 0.0 else f"{side_cost:.2f} bps per side modeled",
            {"per_side_cost_bps": side_cost},
        ),
        check(
            "net_profitability", "economics", "pass" if total_return > 0.0 else "fail",
            f"net total return {total_return:+.2%} after costs", {"total_return": total_return},
        ),
    ]
    be = float(breakeven["breakeven_bps"])
    if total_return <= 0.0:
        margin = check("cost_margin", "economics", "skip", "not profitable after costs", breakeven)
    else:
        thin = be < 2.0 * max(side_cost, 1.0)
        margin = check(
            "cost_margin", "economics", "warn" if thin else "pass",
            f"break-even cost {be:.2f} bps per side vs {side_cost:.2f} modeled", breakeven,
        )
    rows.append(margin)
    if total_return <= 0.0:
        rows.append(check("delay_sensitivity", "economics", "skip", "not profitable after costs", delay))
    else:
        rows.append(
            check(
                "delay_sensitivity", "economics", delay["status"],
                "profit vanishes with 1 bar delay" if delay["status"] == "warn" else "survives 1 bar execution delay",
                delay,
            )
        )
    return rows


def timing_row(timing: dict[str, Any] | None) -> dict[str, Any]:
    """Timing significance against circular shifts (``None``: not profitable, not run)."""
    if timing is None:
        return check("timing_significance", "statistics", "skip", "not profitable after costs")
    if timing["status"] == "skip":
        return check("timing_significance", "statistics", "skip", "timing: no positions or too few bars", timing)
    summary = (
        f"beats {timing['share_beaten']:.0%} of {timing['n_shifts']} shifted copies of its positions"
        f" (p {timing['p_value']:.3f})"
    )
    return check("timing_significance", "statistics", timing["status"], summary, timing)


def benchmark_row(total_return: float, sharpe: float, bench: dict[str, Any]) -> dict[str, Any]:
    """Buy-and-hold on the same data and costs, for context (never changes the verdict)."""
    summary = (
        f"buy & hold {bench['total_return']:+.2%} (Sharpe {bench['sharpe_annualized']:.2f})"
        f" vs strategy {total_return:+.2%} (Sharpe {sharpe:.2f})"
    )
    details = {k: bench[k] for k in ("total_return", "max_drawdown", "sharpe_annualized")}
    details["excess_return"] = total_return - bench["total_return"]
    return check("benchmark", "statistics", "info", summary, details)


def period_row(breakdown: dict[str, Any], total_return: float) -> dict[str, Any]:
    """Warn when the whole profit comes from one period."""
    rows = breakdown["periods"]
    if total_return <= 0.0:
        return check("period_consistency", "statistics", "skip", "not profitable after costs")
    if len(rows) < 3:
        return check("period_consistency", "statistics", "skip", "fewer than 3 periods")
    rets = np.array([r["return"] for r in rows])
    best = int(np.argmax(rets))
    rest = float(np.prod(np.delete(1.0 + rets, best)) - 1.0)
    positive = int(np.count_nonzero(rets > 0))
    details = {"best_period": rows[best]["period"], "return_without_best": rest, "positive_periods": positive, "periods": len(rows)}
    if rest <= 0.0:
        summary = f"profit comes from one period ({rows[best]['period']}); the other {len(rows) - 1} return {rest:+.2%}"
        return check("period_consistency", "statistics", "warn", summary, details)
    return check("period_consistency", "statistics", "pass", f"profitable in {positive} of {len(rows)} periods", details)


def statistics_rows(
    dsr: dict[str, Any], n_closed: int, min_trades: int, trials_declared: bool, holdout: dict[str, Any]
) -> list[dict[str, Any]]:
    """Sample size, Deflated Sharpe, trial disclosure, holdout consistency."""
    d = float(dsr["deflated_sharpe"])
    d_status = "pass" if d >= 0.95 else ("warn" if d >= 0.5 else "fail")
    ho_bad = holdout["train_sharpe"] > 0.0 and holdout["holdout_sharpe"] <= 0.0
    return [
        check(
            "sample_size", "statistics", "pass" if n_closed >= min_trades else "fail",
            f"{n_closed} closed trades (min {min_trades})", {"n_closed_trades": n_closed, "min_trades": min_trades},
        ),
        check(
            "deflated_sharpe", "statistics", d_status,
            f"deflated Sharpe {d:.3f} over {dsr['n_trials']} trial(s)", dsr,
        ),
        check(
            "trials_disclosed", "statistics", "pass" if trials_declared else "info",
            "n_trials declared" if trials_declared else "n_trials not declared (assumed 1)",
        ),
        check(
            "holdout_consistency", "statistics", "warn" if ho_bad else "pass",
            f"Sharpe/bar train {holdout['train_sharpe']:+.4f} vs holdout {holdout['holdout_sharpe']:+.4f}",
            holdout,
        ),
    ]


def next_actions(checks: list[dict[str, Any]]) -> list[str]:
    """Ordered fix-it list for failing then warning checks."""
    out: list[str] = []
    for wanted in ("fail", "warn"):
        for row in checks:
            if row["status"] != wanted:
                continue
            action = NEXT_ACTIONS.get(row["id"], "")
            if row["id"] == "lookahead_static_lint":
                lines = sorted({f["line"] for f in row["details"].get("findings", [])})
                action = f"{action} Lines: {', '.join(str(x) for x in lines)}."
            if action and action not in out:
                out.append(action)
    return out


__all__ = [
    "NEXT_ACTIONS",
    "accuracy_row",
    "benchmark_row",
    "check",
    "data_integrity",
    "economics_rows",
    "lint_row",
    "next_actions",
    "period_row",
    "probe_row",
    "statistics_rows",
    "survivorship_row",
    "timing_row",
]
