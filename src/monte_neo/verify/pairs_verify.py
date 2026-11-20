"""Econometric checks for pairs and stat-arb strategies, added to ``verify --legs`` as ``--pairs-checks``.

The accounting check in :mod:`monte_neo.verify.legs` asks whether the reported P&L is what the legs earned. These checks
ask whether there is a relationship to trade at all, whether it survives in time, whether the winner was picked from
many candidates, and whether the P&L survives a late second leg and a short that cannot be borrowed.

Statuses are chosen so that an honest pair is never rejected on econometrics alone: the relationship checks are
``statistics`` rows (a failure gives ``NEEDS_MORE_EVIDENCE``, not ``REJECT``), the execution checks are ``economics``
rows that only warn.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check
from monte_neo.verify.legs import rederive
from monte_neo.verify.pairs_breaks import bai_perron_means, break_onset, chow_test, cusum_test, sup_wald_test
from monte_neo.verify.pairs_johansen import johansen
from monte_neo.verify.pairs_legging import DEFAULT_SCAN_BARS, borrow_scenario, legging_scan
from monte_neo.verify.pairs_selection import selection_report
from monte_neo.verify.pairs_stability import rolling_cointegration, rolling_hedge_ratio
from monte_neo.verify.pairs_unitroot import engle_granger, half_life, kpss_test

MIN_BARS = 120
HEDGE_CV_WARN = 0.25
ROLLING_SHARE_PASS = 0.6
LEGGING_DAMAGE_WARN = 0.3
MIN_SCAN_BARS = 0.001
NEXT_ACTIONS: dict[str, str] = {
    "cointegration_eg": "The spread is not shown to be stationary: there is no long-run relationship to trade. Test the pair out of sample, choose another pair, or check that both legs are the same kind of price (adjusted, same currency).",
    "cointegration_johansen": "Johansen finds no cointegrating relation among the legs: the basket has no stable combination to trade. Reduce the basket or test other legs.",
    "spread_half_life": "The spread reverts too slowly (or not at all) for the length of the sample: few full reversions are observed, so the profit rests on a handful of trades. Use more history or a faster pair.",
    "hedge_ratio_stability": "The hedge ratio wanders between windows: a fixed ratio will not hold, and a re-fitted one needs the leg-accounting check. Test with the ratio frozen on the earlier part of the history.",
    "rolling_cointegration": "The pair is cointegrated only in part of the history: find what changed in the windows that fail (listing, merger, regime) and trade only while the link is monitored live.",
    "structural_break_spread": "The spread's level moved at the date named in the row: the pair before and after it are different relationships. Re-estimate after the date, or stop trading the pair when a break is detected.",
    "structural_break_hedge": "The relationship estimated on the first part of the sample stopped holding at the date named in the row: the hedge ratio was not stable out of sample. Judge the strategy only on data after the date, or re-estimate the hedge in a way the live system can follow.",
    "chow_known_date": "The spread's mean differs before and after the date you gave: treat the two periods as separate relationships.",
    "pair_selection": "The Sharpe ratio does not survive the number of pairs that were screened: report how many pairs and variants were tried (--pairs-tested), and confirm the winner on data that played no part in the screening.",
    "legging_risk": "The profit shrinks a lot when the second leg is late: execute both legs together (one venue, one order) or model the leg delay in the backtest.",
    "borrow_risk": "The profit shrinks a lot with a borrow fee or when the short cannot be borrowed: check borrow availability and the fee for the short leg and include them in the backtest.",
}


@dataclass(frozen=True)
class PairsOptions:
    """Settings of :func:`pairs_checks` (all optional)."""

    pairs_tested: int | None = None
    variants_per_pair: int = 1
    legging_delay_bars: float | None = None
    legging_delay_ms: float | None = None
    bar_ms: float | None = None  # bar length; read from the dates when omitted
    borrow_bps: float = 0.0
    borrow_unavailable: float = 0.0
    break_date: str | None = None
    window: int | None = None


def _date(body: pd.DataFrame, i: int) -> str:
    return str(body.index[int(min(max(i, 0), len(body) - 1))])


def _log_prices(body: pd.DataFrame) -> tuple[list[str], np.ndarray]:
    legs = [c[3:] for c in body.columns if c.startswith("px_")]
    return legs, np.log(body[[f"px_{leg}" for leg in legs]].to_numpy(dtype=np.float64))


def _relationship_rows(body: pd.DataFrame, opts: PairsOptions) -> tuple[list[dict[str, Any]], dict[str, Any], np.ndarray]:
    legs, logs = _log_prices(body)
    rows: list[dict[str, Any]] = []
    eg = engle_granger(logs[:, 0], logs[:, 1])
    kp = kpss_test(eg["spread"])
    r = eg["reject"]
    stat = "pass" if r[0.05] and not kp["reject"][0.05] else "warn" if r[0.10] else "fail"
    rows.append(check(
        "cointegration_eg", "statistics", stat,
        f"Engle-Granger t={eg['stat']:.2f} (5% critical {eg['critical'][0.05]:.2f}), p {eg['pvalue_bucket']}; KPSS {kp['stat']:.2f}"
        f" ({'rejects' if kp['reject'][0.05] else 'does not reject'} stationarity at 5%); hedge ratio {eg['beta']:.3f} of {legs[1]} per {legs[0]}.",
        {"stat": eg["stat"], "critical": eg["critical"], "lag": eg["lag"], "beta": eg["beta"], "alpha": eg["alpha"], "pvalue_bucket": eg["pvalue_bucket"], "kpss": {"stat": kp["stat"], "critical": kp["critical"], "lags": kp["lags"]}, "legs": legs[:2]},
    ))
    if logs.shape[1] >= 3:
        jo = johansen(logs[:, :5])
        rows.append(check(
            "cointegration_johansen", "statistics", "pass" if jo["rank"] >= 1 else "fail",
            f"Johansen trace test (95%) finds {jo['rank']} cointegrating relation(s) among {logs.shape[1]} legs.",
            {"rank": jo["rank"], "trace": jo["trace"], "trace_critical": jo["trace_critical"], "max_eig": jo["max_eig"], "max_eig_critical": jo["max_eig_critical"], "vector": jo["vector"], "n_obs": jo["n_obs"]},
        ))
    hl = half_life(eg["spread"])
    n = len(body)
    hl_bars = hl["half_life"]
    hl_status = "pass" if hl["mean_reverting"] and hl_bars <= n / 10 else "warn"
    hl_text = f"{hl_bars:.1f} bars" if hl["mean_reverting"] else "the spread does not revert"
    rows.append(check("spread_half_life", "statistics", hl_status, f"half-life of mean reversion: {hl_text} (sample {n} bars).", {"half_life_bars": hl_bars, "b": hl["b"], "bars": n}))
    hr = rolling_hedge_ratio(logs[:, 0], logs[:, 1], opts.window)
    unstable = hr["cv"] > HEDGE_CV_WARN
    rows.append(check(
        "hedge_ratio_stability", "statistics", "warn" if unstable else "pass",
        f"hedge ratio over {hr['beta'].size} windows of {hr['window']} bars: median {hr['median']:.3f}, relative spread {hr['cv']:.0%}, drift {hr['drift']:+.0%}.",
        {"median": hr["median"], "cv": hr["cv"], "drift": hr["drift"], "window": hr["window"], "min": float(np.nanmin(hr["beta"])), "max": float(np.nanmax(hr["beta"]))},
    ))
    rc = rolling_cointegration(logs[:, 0], logs[:, 1], opts.window)
    last = _date(body, rc["last_reject_end"]) if rc["last_reject_end"] >= 0 else "never"
    rows.append(check(
        "rolling_cointegration", "statistics", "pass" if rc["share"] >= ROLLING_SHARE_PASS else "warn",
        f"Engle-Granger rejects at 5% in {rc['share']:.0%} of {rc['stat'].size} windows of {rc['window']} bars; last rejecting window ends {last}.",
        {"share": rc["share"], "window": rc["window"], "windows": int(rc["stat"].size), "last_reject_end": last},
    ))
    return rows, eg, logs


def _break_row(check_id: str, body: pd.DataFrame, spread: np.ndarray, what: str) -> dict[str, Any]:
    cu, sw = cusum_test(spread), sup_wald_test(spread)
    bp = bai_perron_means(spread)
    when = _date(body, break_onset(spread, sw["index"]))
    strong = cu["reject"][0.01] and sw["reject"][0.01] and sw["shift_sd"] >= 1.0
    weak = cu["reject"][0.05] or sw["reject"][0.05]
    status = "fail" if strong else "warn" if weak else "pass"
    if status == "pass":
        summary = f"{what}: no break found (CUSUM {cu['stat']:.2f}, sup-Wald {sw['stat']:.1f})."
    else:
        summary = f"{what}: the relationship changed around {when} (mean shift {sw['shift_sd']:.1f} sd; CUSUM {cu['stat']:.2f}, sup-Wald {sw['stat']:.1f})."
    return check(
        check_id, "statistics", status, summary,
        {"break_date": when if status != "pass" else None, "cusum": {"stat": cu["stat"], "critical": cu["critical"]}, "sup_wald": {"stat": sw["stat"], "critical": sw["critical"], "shift_sd": sw["shift_sd"]}, "bai_perron_dates": [_date(body, b) for b in bp["breaks"]]},
    )


def _break_rows(body: pd.DataFrame, logs: np.ndarray, eg: dict[str, Any], opts: PairsOptions) -> list[dict[str, Any]]:
    rows = [_break_row("structural_break_spread", body, eg["spread"], "spread level")]
    half = len(body) // 2
    x1, y1 = logs[:half, 1], logs[:half, 0]
    xc = x1 - x1.mean()
    beta = float(xc @ (y1 - y1.mean()) / (xc @ xc))
    frozen = logs[:, 0] - beta * logs[:, 1]
    rows.append(_break_row("structural_break_hedge", body, frozen, f"spread with the hedge ratio frozen on the first {half} bars ({beta:.3f})"))
    if opts.break_date:
        idx = int(body.index.searchsorted(pd.Timestamp(opts.break_date)))
        ch = chow_test(eg["spread"], idx)
        broke = ch["reject"][0.01]
        rows.append(check(
            "chow_known_date", "statistics", "warn" if broke else "pass",
            f"Chow test at {opts.break_date}: Wald {ch['stat']:.1f} (1% critical {ch['critical'][0.01]})" + ("; the spread level differs before and after." if broke else "; no shift."),
            {"stat": ch["stat"], "critical": ch["critical"], "shift": ch["shift"], "date": opts.break_date},
        ))
    return rows


def _execution_rows(body: pd.DataFrame, opts: PairsOptions, ppy: float, pnl: str) -> list[dict[str, Any]]:
    from monte_neo.verify.arrival import SCAN_MS

    rows: list[dict[str, Any]] = []
    base = float(rederive(body, pnl=pnl).sum())
    bar_ms = opts.bar_ms or float(body.index.to_series().diff().median() / pd.Timedelta(milliseconds=1))
    delay = opts.legging_delay_bars
    if delay is None and opts.legging_delay_ms is not None:
        delay = opts.legging_delay_ms / bar_ms
    latency = [ms / bar_ms for ms in SCAN_MS[1:] if ms / bar_ms >= MIN_SCAN_BARS]
    scan_bars = tuple(sorted({*DEFAULT_SCAN_BARS, *([delay] if delay else []), *latency}))
    scan = legging_scan(body, scan_bars, pnl=pnl)
    test = 1.0 if delay is None else delay
    at = min(scan, key=lambda row: abs(row["delay_bars"] - test))
    if base <= 0.0:
        rows.append(check("legging_risk", "economics", "skip", "the legs do not earn a profit, so a late second leg cannot be priced.", {"scan": scan}))
    else:
        bad = at["total"] <= 0.0 or at["damage_share"] > LEGGING_DAMAGE_WARN
        rows.append(check(
            "legging_risk", "economics", "warn" if bad else "pass",
            f"with the second leg {at['delay_bars']:g} bar(s) late the P&L changes by {-at['damage_share']:+.0%}" + (" and turns into a loss." if at["total"] <= 0.0 else "."),
            {"test_delay_bars": at["delay_bars"], "scan": scan},
        ))
    if opts.borrow_bps > 0.0 or opts.borrow_unavailable > 0.0:
        bo = borrow_scenario(body, borrow_bps=opts.borrow_bps, unavailable_share=opts.borrow_unavailable, periods_per_year=ppy, pnl=pnl)
        if base <= 0.0:
            rows.append(check("borrow_risk", "economics", "skip", "the legs do not earn a profit, so the borrow cost cannot be priced.", bo))
        else:
            bad = bo["total"] <= 0.0 or bo["damage_share"] > LEGGING_DAMAGE_WARN
            rows.append(check(
                "borrow_risk", "economics", "warn" if bad else "pass",
                f"with a {opts.borrow_bps:g} bps annual borrow fee and the short unavailable {opts.borrow_unavailable:.0%} of the time the P&L changes by {-bo['damage_share']:+.0%}.",
                bo,
            ))
    return rows


def pairs_checks(body: pd.DataFrame, opts: PairsOptions | None = None, *, periods_per_year: float = 252.0, pnl: str = "log") -> list[dict[str, Any]]:
    """Run the econometric, selection-bias and execution checks on a legs table from :func:`~monte_neo.verify.legs.load_legs`.

    Args:
        body: The legs table (the first two legs form the tested pair; 3 or more add the Johansen test).
        opts: See :class:`PairsOptions`.
        periods_per_year: Bars per year (for the borrow fee and the Sharpe ratio).
        pnl: ``"log"`` or ``"simple"`` accounting, as in ``verify --legs``.

    Returns:
        Check rows: ``cointegration_eg``, ``cointegration_johansen`` (3+ legs), ``spread_half_life``,
        ``hedge_ratio_stability``, ``rolling_cointegration``, ``structural_break_spread``, ``structural_break_hedge``,
        ``chow_known_date`` (with a date), ``pair_selection``, ``legging_risk`` and ``borrow_risk`` (with borrow settings).
    """
    opts = opts or PairsOptions()
    if len(body) < MIN_BARS:
        raise ValueError(f"only {len(body)} bars; the pairs checks need at least {MIN_BARS}")
    if sum(c.startswith("px_") for c in body.columns) < 2:
        raise ValueError("the pairs checks need at least two legs")
    rows, eg, logs = _relationship_rows(body, opts)
    rows += _break_rows(body, logs, eg, opts)
    ret = rederive(body, pnl=pnl)
    if opts.pairs_tested is None:
        rows.append(check("pair_selection", "statistics", "info", "the number of pairs screened was not declared (assumed 1): pass --pairs-tested so the Sharpe ratio is deflated by the selection."))
    else:
        sel = selection_report(ret, opts.pairs_tested, variants_per_pair=opts.variants_per_pair, periods_per_year=periods_per_year)
        d = float(sel["deflated_sharpe"])
        rows.append(check(
            "pair_selection", "statistics", "pass" if d >= 0.95 else "warn" if d >= 0.5 else "fail",
            f"deflated Sharpe {d:.3f} after {opts.pairs_tested} pair(s) x {opts.variants_per_pair} variant(s) = {sel['n_trials']} trials (single pair: {sel['deflated_sharpe_single']:.3f}).",
            sel,
        ))
    return rows + _execution_rows(body, opts, periods_per_year, pnl)


__all__ = ["NEXT_ACTIONS", "PairsOptions", "pairs_checks"]
