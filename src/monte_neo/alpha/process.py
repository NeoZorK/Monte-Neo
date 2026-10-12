"""Family G: data and research process of an alpha.

* G1 ``universe_lookahead``: does the portfolio hold symbols outside their index membership window?
* G2 ``classification_lookahead``: are sector or industry groups dated, or is today's map applied to the past?
* G3 ``cross_market_close_alignment``: does a score use prices of markets that close after the traded market?
* G5 ``post_discovery_decay``: did the edge shrink after the anomaly was published or found?
* G6 ``research_hygiene``: pre-registration, trial ledger and holdout practices.

All checks judge the weights of the score's portfolio (T x N, ``w[t-1]`` earns bar ``t``). Deterministic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from monte_neo.alpha.implementability_common import ann_sharpe, clean_weights, gross_series, simple_returns
from monte_neo.alpha.panel import Panel
from monte_neo.verify.checks import check
from monte_neo.verify.cutoff import _boot_sharpes, _sharpe, parse_cutoff
from monte_neo.verify.ingest import _read_table
from monte_neo.verify.market import SYMBOL_ALIASES

LONG_HISTORY_YEARS = 2.0
MIN_SIDE_BARS = 60
DECAY_WARN = 0.5
SPREAD_HOURS = 4.0
EDGE_SHARPE = 0.3
INTRADAY_PPY = 400.0
HYGIENE_WARN = 1
EXCHANGES: dict[str, tuple[str, str]] = {
    "XNYS": ("America/New_York", "16:00"),
    "XLON": ("Europe/London", "16:30"),
    "XETR": ("Europe/Berlin", "17:30"),
    "XTKS": ("Asia/Tokyo", "15:00"),
    "XHKG": ("Asia/Hong_Kong", "16:00"),
    "CRYPTO": ("UTC", "00:00"),
}
NEXT_ACTIONS: dict[str, str] = {
    "universe_lookahead": "Rebuild the universe point-in-time: keep delisted names and trade a symbol only inside its index membership window (--membership).",
    "classification_lookahead": "Use sector or industry maps with as-of dates (point-in-time), not today's classification applied to the past.",
    "cross_market_close_alignment": "Lag the score of the earlier-closing market by one bar, or build the cross-market input from prices known before that market's close.",
    "post_discovery_decay": "Judge the edge on the period after publication or discovery; expect decay and size the strategy on the post-discovery Sharpe.",
    "research_hygiene": "Register the hypothesis before the first run, keep the trial ledger, and reserve a holdout you query once.",
}


def load_membership(path: str | Path | pd.DataFrame) -> pd.DataFrame:
    """Read universe membership windows: columns ``symbol``, ``start``, ``end``.

    Args:
        path: CSV or parquet path (or a DataFrame). An empty ``end`` means the symbol is still a member; an
            empty ``start`` means a member since before the data begins.

    Returns:
        DataFrame with ``symbol`` (str) and naive datetime ``start`` / ``end`` (NaT = open).

    Raises:
        ValueError: a required column is missing or a date is unparseable.
    """
    df = path.copy() if isinstance(path, pd.DataFrame) else _read_table(Path(path))
    df.columns = [str(c).strip().lower() for c in df.columns]
    scol = next((c for c in SYMBOL_ALIASES if c in df.columns), None)
    if scol is None or "start" not in df.columns or "end" not in df.columns:
        raise ValueError(f"membership needs symbol, start and end columns; found: {', '.join(df.columns)}")
    out = pd.DataFrame({"symbol": df[scol].astype(str).str.strip()})
    for col in ("start", "end"):
        raw = df[col]
        parsed = pd.to_datetime(raw.replace("", np.nan), errors="coerce", utc=True)
        if int((parsed.isna() & raw.notna() & (raw.astype(str).str.strip() != "")).sum()):
            raise ValueError(f"unparseable dates in membership column '{col}'")
        out[col] = parsed.dt.tz_localize(None)
    return out


def _inside(panel: Panel, membership: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Boolean (T, N) membership matrix; symbols absent from the table are returned as unknown."""
    inside = np.zeros(panel.close.shape, dtype=bool)
    known = set(membership["symbol"])
    col = {s: j for j, s in enumerate(panel.symbols)}
    for row in membership.itertuples(index=False):
        j = col.get(row.symbol)
        if j is None:
            continue
        ok = np.ones(len(panel.dates), dtype=bool)
        if pd.notna(row.start):
            ok &= np.asarray(panel.dates >= row.start)
        if pd.notna(row.end):
            ok &= np.asarray(panel.dates <= row.end)
        inside[:, j] |= ok
    unknown = [s for s in panel.symbols if s not in known]
    for s in unknown:
        inside[:, col[s]] = True
    return inside, unknown


def universe_lookahead(panel: Panel, w: np.ndarray, membership: pd.DataFrame | None) -> dict[str, Any]:
    """G1: held symbols outside their membership window fail; without membership a survivor-looking universe warns."""
    if membership is not None:
        inside, unknown = _inside(panel, membership)
        bad = (np.abs(w) > 0) & ~inside
        n_pos, n_bars = int(bad.sum()), int(bad.any(axis=1).sum())
        syms = [panel.symbols[j] for j in np.flatnonzero(bad.any(axis=0))]
        details = {"violating_positions": n_pos, "violating_bars": n_bars, "violating_symbols": syms[:20], "n_violating_symbols": len(syms), "symbols_not_in_membership": unknown[:20]}
        if n_pos:
            return check("universe_lookahead", "lookahead", "fail", f"the portfolio holds symbols outside their membership window: {n_pos} positions on {n_bars} bars across {len(syms)} symbols", details)
        return check("universe_lookahead", "lookahead", "pass", "every held symbol is inside its membership window", details)
    live = np.isfinite(panel.close)
    first = live.argmax(axis=0)
    last = len(panel.dates) - 1 - live[::-1].argmax(axis=0)
    years = (panel.dates[-1] - panel.dates[0]).days / 365.25
    late_start, early_end = int((first > 0).sum()), int((last < len(panel.dates) - 1).sum())
    details = {"years": float(years), "symbols_starting_late": late_start, "symbols_ending_early": early_end}
    if years > LONG_HISTORY_YEARS and not late_start and not early_end:
        return check("universe_lookahead", "lookahead", "warn", f"the universe looks like today's members ({len(panel.symbols)} symbols, none added or delisted over {years:.1f} years): survivorship and selection look-ahead; pass --membership", details)
    return check("universe_lookahead", "lookahead", "info", f"no membership file given; {late_start} symbols start late and {early_end} end early, point-in-time membership not verified (pass --membership)", details)


def classification_lookahead(groups: pd.DataFrame | str | Path | None) -> dict[str, Any]:
    """G2: group maps without as-of dates apply today's classification to the past."""
    if groups is None:
        return check("classification_lookahead", "lookahead", "skip", "no groups file given")
    df = groups.copy() if isinstance(groups, pd.DataFrame) else _read_table(Path(groups))
    df.columns = [str(c).strip().lower() for c in df.columns]
    scol = next((c for c in SYMBOL_ALIASES if c in df.columns), None)
    if scol is None:
        raise ValueError(f"groups need a symbol column; found: {', '.join(df.columns)}")
    gcol = next((c for c in df.columns if c not in (scol, "as_of", "asof")), None)
    dcol = next((c for c in ("as_of", "asof") if c in df.columns), None)
    details: dict[str, Any] = {"symbols": int(df[scol].nunique()), "groups": int(df[gcol].nunique()) if gcol else 0}
    if dcol is None or df[dcol].isna().all():
        return check("classification_lookahead", "lookahead", "warn", "the group mapping has no as-of dates: today's classification is applied to the past", details)
    details["as_of_dates"] = int(df[dcol].nunique())
    return check("classification_lookahead", "lookahead", "info", f"{details['symbols']} symbols in {details['groups']} groups with {details['as_of_dates']} as-of dates", details)


def close_utc_minutes(exchange: str, day: datetime) -> float:
    """UTC minute of the day at which ``exchange`` (name or ``HH:MM`` UTC) closes on ``day``."""
    name = exchange.strip()
    if name.upper() in EXCHANGES:
        tz, hhmm = EXCHANGES[name.upper()]
    else:
        tz, hhmm = "UTC", name
    h, m = (int(x) for x in hhmm.split(":"))
    local = datetime(day.year, day.month, day.day, h, m, tzinfo=ZoneInfo(tz))
    utc = local.astimezone(UTC)
    return utc.hour * 60.0 + utc.minute


def _spread_hours(names: set[str], year: int) -> tuple[float, dict[str, list[float]]]:
    """Largest gap in close time between exchanges, over a winter and a summer day (DST aware)."""
    times: dict[str, list[float]] = {n: [] for n in names}
    spread = 0.0
    for month in (1, 7):
        day = datetime(year, month, 15)
        vals = {n: close_utc_minutes(n, day) for n in names}
        for n, v in vals.items():
            times[n].append(v / 60.0)
        spread = max(spread, (max(vals.values()) - min(vals.values())) / 60.0)
    return spread, times


def cross_market_close_alignment(panel: Panel, w: np.ndarray, exchanges: dict[str, str] | None, ppy: float) -> dict[str, Any]:
    """G3: an edge that exists only without a one-bar lag, across markets with different closes."""
    cid = "cross_market_close_alignment"
    if not exchanges:
        return check(cid, "lookahead", "skip", "no exchange or close-time map given")
    if ppy > INTRADAY_PPY:
        return check(cid, "lookahead", "skip", "intraday bars: close alignment applies to daily bars")
    names = {exchanges[s] for s in panel.symbols if s in exchanges}
    if len(names) < 2:
        return check(cid, "lookahead", "skip", "a single exchange: closes are aligned")
    spread, times = _spread_hours(names, int(panel.dates[0].year))
    details: dict[str, Any] = {"close_hours_utc": times, "max_close_gap_hours": spread}
    if spread <= SPREAD_HOURS:
        return check(cid, "lookahead", "pass", f"exchange closes differ by {spread:.1f} h at most", details)
    ret = simple_returns(panel.close)
    lagged = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
    s_now, s_lag = ann_sharpe(gross_series(w, ret), ppy), ann_sharpe(gross_series(lagged, ret), ppy)
    details.update(sharpe=s_now, sharpe_lagged_one_bar=s_lag)
    text = f"Sharpe {s_now:.2f}, {s_lag:.2f} with all scores lagged one bar; closes differ by {spread:.1f} h"
    if s_now > EDGE_SHARPE and s_lag < 0.5 * s_now:
        status = "fail" if s_lag <= 0.0 else "warn"
        return check(cid, "lookahead", status, f"{text}: the edge exists only without the lag, the signal at the Tokyo close uses New York prices of the same date", details)
    return check(cid, "lookahead", "pass", f"{text}: the edge does not depend on same-date prices of later-closing markets", details)


def post_discovery_decay(panel: Panel, w: np.ndarray, discovery_date: str | None, ppy: float, seed: int = 0) -> dict[str, Any]:
    """G5: Sharpe before and after the discovery date, with the block bootstrap of ``verify.cutoff``."""
    cid = "post_discovery_decay"
    if not discovery_date:
        return check(cid, "statistics", "skip", "no discovery date given")
    when = parse_cutoff(discovery_date)
    r = gross_series(w, simple_returns(panel.close))
    before = np.asarray(panel.dates < when)
    pre, post = r[before], r[~before]
    details: dict[str, Any] = {"discovery_date": when.date().isoformat(), "bars_before": int(pre.size), "bars_after": int(post.size)}
    if pre.size < MIN_SIDE_BARS or post.size < MIN_SIDE_BARS:
        return check(cid, "statistics", "skip", f"need {MIN_SIDE_BARS} bars on each side of the discovery date: {pre.size} before, {post.size} after", details)
    rng = np.random.default_rng(seed)
    s_pre, s_post = _sharpe(pre, ppy), _sharpe(post, ppy)
    p_value = float(np.mean(_boot_sharpes(pre, ppy, rng) - _boot_sharpes(post, ppy, rng) <= 0.0))
    details.update(sharpe_before=s_pre, sharpe_after=s_post, p_value_drop=p_value)
    text = f"Sharpe {s_pre:.2f} before the discovery date {details['discovery_date']}, {s_post:.2f} after (p {p_value:.3f})"
    if s_pre <= 0.0:
        return check(cid, "statistics", "info", f"{text}: no edge before discovery, decay undefined", details)
    decay = 1.0 - s_post / s_pre
    details["decay"] = decay
    note = f"decay {decay * 100:.0f}% (McLean and Pontiff found about a third on average after publication)"
    if decay > DECAY_WARN:
        return check(cid, "statistics", "warn", f"{text}: {note}; more than half of the edge is gone", details)
    return check(cid, "statistics", "info", f"{text}: {note}", details)


def research_hygiene(hygiene: dict[str, Any] | None) -> dict[str, Any]:
    """G6: score 0-4 for pre-registration, registration order, a trial ledger and a holdout."""
    cid = "research_hygiene"
    if not hygiene:
        return check(cid, "statistics", "skip", "no research-process information given")
    practices = {
        "registered": hygiene.get("registered") is True,
        "registered_before_first_run": hygiene.get("registered_before_first_run") is True,
        "trial_ledger": (hygiene.get("ledger_variants") or 0) > 0,
        "holdout_used": hygiene.get("holdout_used") is True,
    }
    missing = [k for k, ok in practices.items() if not ok]
    score = 4 - len(missing)
    details = {"score": score, "missing": missing, "ledger_variants": hygiene.get("ledger_variants")}
    text = f"research hygiene {score}/4" + (f"; missing: {', '.join(missing)}" if missing else "")
    return check(cid, "statistics", "warn" if score <= HYGIENE_WARN else "info", text, details)


def run_process(
    panel: Panel,
    weights: np.ndarray,
    *,
    membership: pd.DataFrame | str | Path | None = None,
    groups: pd.DataFrame | str | Path | None = None,
    exchanges: dict[str, str] | None = None,
    discovery_date: str | None = None,
    hygiene: dict[str, Any] | None = None,
    ppy: float | None = None,
) -> list[dict[str, Any]]:
    """Run family G (G1, G2, G3, G5, G6).

    Args:
        panel: The aligned panel.
        weights: Portfolio weights (T x N); ``w[t-1]`` earns bar ``t``.
        membership: Optional membership windows (symbol, start, end) for G1.
        groups: Optional symbol-to-group map with ``as_of`` dates for G2.
        exchanges: Optional symbol -> exchange name (XNYS, XLON, XETR, XTKS, XHKG, CRYPTO) or ``HH:MM`` UTC close.
        discovery_date: Publication or discovery date of the anomaly (``YYYY-MM[-DD]``) for G5.
        hygiene: Optional dict: registered, registered_before_first_run, ledger_variants, holdout_used.
        ppy: Bars per year; default inferred from the panel.

    Returns:
        Check rows.
    """
    w = clean_weights(weights)
    bars = float(ppy) if ppy else panel.periods_per_year
    mem = None if membership is None else load_membership(membership)
    return [
        universe_lookahead(panel, w, mem),
        classification_lookahead(groups),
        cross_market_close_alignment(panel, w, exchanges, bars),
        post_discovery_decay(panel, w, discovery_date, bars),
        research_hygiene(hygiene),
    ]


__all__ = ["NEXT_ACTIONS", "load_membership", "run_process"]
