"""Turn raw probe / engine outputs into ``strategy-verdict/1`` check rows."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.backtest.model import ExecutionModel

# Fix-it hints an agent can act on, keyed by check id.
NEXT_ACTIONS: dict[str, str] = {
    "data_integrity": "Clean the OHLCV: drop NaN rows, non-positive prices and bars with high < low.",
    "determinism": "Make the signal deterministic: seed every RNG and avoid wall-clock or I/O inside signal().",
    "lookahead_truncation": "The signal at bar t changes when later bars are removed: compute features only from rows <= t (no shift(-k), centered windows, bfill or full-sample stats).",
    "lookahead_perturbation": "Past signals change when the future is rewritten: remove whole-series statistics (mean/std/min/max over all rows) and future-dependent fills.",
    "lookahead_static_lint": "Fix the flagged source lines (negative shift, center=True, backward fill) and re-run verify.",
    "implausible_accuracy": "Next-bar hit rate is too high to be real: look for leakage of the next bar's close/open into the signal.",
    "costs_modeled": "Re-run with realistic costs (e.g. commission_bps=5, slippage_bps=5 for liquid crypto).",
    "net_profitability": "The strategy loses money after costs: reduce turnover or find a stronger edge.",
    "cost_margin": "Edge barely covers costs: cut turnover or test with higher slippage before trusting it.",
    "delay_sensitivity": "Profit disappears with one bar of execution delay: the edge lives in fill timing.",
    "sample_size": "Too few closed trades for statistics: test on more history or more instruments.",
    "deflated_sharpe": "Sharpe does not survive the number of variants tried: test out-of-sample or reduce the search space.",
    "trials_disclosed": "Pass n_trials = number of variants you tried (parameters, rules, assets) so selection bias is priced in.",
    "holdout_consistency": "Recent (holdout) performance does not confirm the earlier sample: check for regime dependence or overfit.",
    "walk_forward_oos": "Parameters picked on past folds do not hold on the next fold: shrink the grid or prefer robust parameter plateaus.",
}


def check(
    check_id: str, category: str, status: str, summary: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build one check row."""
    return {"id": check_id, "category": category, "status": status, "summary": summary, "details": details or {}}


def data_integrity(ohlc: dict[str, np.ndarray]) -> dict[str, Any]:
    """NaN, non-positive prices and inverted bars."""
    o, h, l, c = (ohlc[k] for k in ("open", "high", "low", "close"))
    stacked = np.vstack([o, h, l, c])
    n_nan = int(np.count_nonzero(~np.isfinite(stacked)))
    n_nonpos = int(np.count_nonzero(np.nan_to_num(stacked, nan=1.0) <= 0.0))
    n_inverted = int(np.count_nonzero(np.nan_to_num(h) < np.nan_to_num(l)))
    bad = n_nan + n_nonpos + n_inverted
    summary = "OHLCV is clean" if not bad else f"{n_nan} NaN, {n_nonpos} non-positive, {n_inverted} high<low values"
    return check(
        "data_integrity", "integrity", "fail" if bad else "pass", summary,
        {"nan_values": n_nan, "non_positive_values": n_nonpos, "inverted_bars": n_inverted},
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


def lint_row(lint: dict[str, Any] | None) -> dict[str, Any]:
    """Wrap static lint findings."""
    if lint is None:
        return check("lookahead_static_lint", "lookahead", "skip", "static lint: no source provided")
    rules = sorted({f["rule"] for f in lint["findings"]})
    summary = "static lint: clean" if not rules else f"static lint: {', '.join(rules)}"
    return check("lookahead_static_lint", "lookahead", lint["status"], summary, lint)


def accuracy_row(acc: dict[str, Any]) -> dict[str, Any]:
    """Wrap the implausible-accuracy smell test."""
    rate = acc.get("hit_rate")
    summary = "next-bar hit rate: too few active bars" if acc["status"] == "skip" else f"next-bar hit rate {rate:.3f}"
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
    rows.append(
        check(
            "delay_sensitivity", "economics", delay["status"],
            "profit vanishes with 1 bar delay" if delay["status"] == "warn" else "survives 1 bar execution delay",
            delay,
        )
    )
    return rows


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
    "check",
    "data_integrity",
    "economics_rows",
    "lint_row",
    "next_actions",
    "probe_row",
    "statistics_rows",
]
