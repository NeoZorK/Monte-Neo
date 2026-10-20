"""Re-derive a strategy's P&L from the positions it held in each leg and compare it with what it reported.

``verify --legs`` is for strategies that trade a spread or a basket (pairs, stat-arb, hedged books), where the reported
return is easy to book wrongly. The most common error is a re-estimated hedge ratio booked as
``position * change of the spread``: the change of the spread contains ``-(d_beta * x + d_alpha)``, a term that comes from
re-fitting the hedge and that no trader can earn ("phantom mean reversion"). Re-deriving the P&L from the legs removes it.
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo._version import __version__
from monte_neo.verify.checks import check
from monte_neo.verify.schema import DISCLAIMER, VERDICT_SCHEMA_ID, aggregate_verdict, to_jsonable
from monte_neo.verify.stats import infer_periods_per_year
from monte_neo.verify.verdict import certificate_id

MIN_BARS = 30
DEFAULT_TOLERANCE = 0.05
SCOPE_NOTE = (
    "Accounting only: the reported P&L was re-derived from the leg positions you gave. Look-ahead in the signal, trading "
    "costs and data quality are not checked here; use the full verify for them."
)
NEXT_ACTIONS: dict[str, str] = {
    "accounting_mismatch": (
        "The reported P&L is not what the legs earn. For a spread with a re-estimated hedge ratio, book "
        "pnl = position.shift(1) * (d_y - beta.shift(1) * d_x), i.e. the quantities held over the bar times the price "
        "changes of the legs, not position * diff(spread). Re-run with the corrected series (--legs-fixed-out writes it)."
    ),
    "derived_significance": "The legs earn too little to tell from luck: judge the strategy on the re-derived series, not on the reported one.",
}


def load_legs(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    """Read a legs table: ``date``, ``px_<leg>`` and ``qty_<leg>`` per leg, ``reported_return``, optional ``cost``.

    ``qty_<leg>`` is the quantity held over the bar that ends at ``date`` (decided at the previous bar), in log-notional
    units (P&L = quantity * change of the log price); ``cost`` is a per-bar cost fraction already inside ``reported_return``.

    Raises:
        ValueError: Missing columns, a leg without prices or quantities, bad dates, non-positive prices, or fewer than
            30 bars.
    """
    df = source.copy() if isinstance(source, pd.DataFrame) else (
        pd.read_parquet(source) if str(source).lower().endswith((".parquet", ".pq")) else pd.read_csv(source)
    )
    df.columns = [str(c).strip() for c in df.columns]
    key = next((c for c in df.columns if c.lower() in ("date", "time", "timestamp", "datetime")), None)
    if key is None:
        raise ValueError("no date column found: add a column named date")
    px = [c[3:] for c in df.columns if c.startswith("px_")]
    qty = [c[4:] for c in df.columns if c.startswith("qty_")]
    if not px:
        raise ValueError("no price columns: add px_<leg> and qty_<leg> for every leg (for example px_y, px_x, qty_y, qty_x)")
    if set(px) != set(qty):
        raise ValueError(f"every leg needs both px_ and qty_ columns; prices for {sorted(px)}, quantities for {sorted(qty)}")
    if "reported_return" not in df.columns:
        raise ValueError("no reported_return column: add the per-bar return the backtest reported")
    dates = pd.to_datetime(df[key], errors="coerce")
    if dates.isna().any():
        raise ValueError(f"{int(dates.isna().sum())} dates cannot be parsed")
    cols = [f"px_{leg}" for leg in px] + [f"qty_{leg}" for leg in px] + ["reported_return"] + (["cost"] if "cost" in df.columns else [])
    body = df[cols].apply(pd.to_numeric, errors="coerce")
    body.index = pd.DatetimeIndex(dates)
    if body.isna().any().any() or not np.isfinite(body.to_numpy()).all():
        raise ValueError("prices, quantities and returns must be finite numbers with no empty cells")
    if (body[[f"px_{leg}" for leg in px]] <= 0).any().any():
        raise ValueError("prices must be positive")
    if body.index.duplicated().any():
        raise ValueError("duplicate dates; keep one row per bar")
    body = body.sort_index()
    if len(body) < MIN_BARS:
        raise ValueError(f"only {len(body)} bars; at least {MIN_BARS} are needed")
    return body


def _legs_of(body: pd.DataFrame) -> list[str]:
    return [c[3:] for c in body.columns if c.startswith("px_")]


def rederive(body: pd.DataFrame, *, pnl: str = "log", shift: int = 0) -> np.ndarray:
    """P&L per bar from the legs: ``sum(quantity * price change)``, for bars ``1..n-1``.

    Args:
        body: A table from :func:`load_legs`.
        pnl: ``"log"`` (quantity in log-notional units, change of the log price) or ``"simple"`` (quantity as a fraction
            of equity, simple price return).
        shift: ``0`` uses the quantity on the same row (held over the bar ending there), ``1`` the previous row's.
    """
    if pnl not in ("log", "simple"):
        raise ValueError("pnl must be 'log' or 'simple'")
    total = np.zeros(len(body) - 1)
    for leg in _legs_of(body):
        px = body[f"px_{leg}"].to_numpy(dtype=np.float64)
        change = np.diff(np.log(px)) if pnl == "log" else px[1:] / px[:-1] - 1.0
        q = body[f"qty_{leg}"].to_numpy(dtype=np.float64)
        total += (q[1:] if shift == 0 else q[:-1]) * change
    if "cost" in body.columns:
        total = total - body["cost"].to_numpy(dtype=np.float64)[1:]
    return total


def _sharpe(r: np.ndarray, ppy: float) -> float:
    sd = float(r.std(ddof=1)) if r.size > 1 else 0.0
    return float(r.mean() / sd * math.sqrt(ppy)) if sd > 0 else 0.0


def _gap_share(rep: np.ndarray, der: np.ndarray) -> float:
    denom = max(abs(float(rep.sum())), abs(float(der.sum())), 1e-12)
    return float((rep.sum() - der.sum()) / denom)


def verify_legs(
    legs: str | Path | pd.DataFrame, *, tolerance: float = DEFAULT_TOLERANCE, pnl: str = "log", periods_per_year: float | None = None
) -> dict[str, Any]:
    """Check that the reported return equals what the legs earn; return a ``strategy-verdict/1`` certificate.

    Args:
        legs: A legs file or table, see :func:`load_legs`.
        tolerance: Largest share of the P&L that may be unexplained, ``(reported - derived) / max(|reported|, |derived|)``
            over the whole record (default 0.05).
        pnl: ``"log"`` or ``"simple"``, see :func:`rederive`.
        periods_per_year: Bars per year; inferred from the dates when omitted.

    Returns:
        The report with checks ``accounting_mismatch`` (integrity, a failure rejects) and ``derived_significance``.
        The corrected series is :func:`write_fixed_returns`.
    """
    body = legs if isinstance(legs, pd.DataFrame) and isinstance(legs.index, pd.DatetimeIndex) else load_legs(legs)
    rep = body["reported_return"].to_numpy(dtype=np.float64)[1:]
    der = rederive(body, pnl=pnl)
    ppy = float(periods_per_year) if periods_per_year else float(infer_periods_per_year(body.index))
    share = _gap_share(rep, der)
    gap = rep - der
    gap_t = float(gap.mean() / (gap.std(ddof=1) / math.sqrt(gap.size))) if gap.std(ddof=1) > 0 else 0.0
    sr_rep, sr_der = _sharpe(rep, ppy), _sharpe(der, ppy)
    t_der = float(der.mean() / (der.std(ddof=1) / math.sqrt(der.size))) if der.std(ddof=1) > 0 else 0.0
    shifted = _gap_share(rep, rederive(body, pnl=pnl, shift=1))
    details = {
        "legs": _legs_of(body), "bars": int(rep.size), "tolerance": float(tolerance),
        "reported_total": float(rep.sum()), "derived_total": float(der.sum()),
        "reported_sharpe": sr_rep, "derived_sharpe": sr_der,
        "unexplained_share": share, "gap_t_stat": gap_t, "share_with_previous_row_quantities": shifted,
    }
    if abs(share) > tolerance:
        what = "inflates" if share > 0 else "understates"
        hint = ""
        if abs(shifted) <= tolerance:
            hint = " The quantities match when read one row earlier: they are probably shifted by one bar."
        mismatch = check(
            "accounting_mismatch", "integrity", "fail",
            f"the reported P&L {what} what the legs earn: reported Sharpe {sr_rep:+.2f}, re-derived {sr_der:+.2f}, "
            f"{abs(share):.0%} of the P&L is unexplained (tolerance {tolerance:.0%}).{hint}",
            details,
        )
    else:
        mismatch = check("accounting_mismatch", "integrity", "pass", f"the reported P&L matches the legs within {tolerance:.0%} (unexplained {abs(share):.1%}).", details)
    sig_status = "pass" if t_der >= 2.0 else "warn"
    significance = check(
        "derived_significance", "statistics", sig_status,
        f"the legs earn Sharpe {sr_der:+.2f} (t-statistic {t_der:+.2f}, {rep.size} bars)"
        + ("." if sig_status == "pass" else ": not distinguishable from zero."),
        {"derived_sharpe": sr_der, "t_stat": t_der},
    )
    checks = [check("legs_scope", "integrity", "info", SCOPE_NOTE), mismatch, significance]
    verdict = aggregate_verdict(checks)
    repro = {
        "engine": "monte-neo", "engine_version": __version__, "n_trials": 1,
        "data_sha256": hashlib.sha256(body.round(12).to_csv().encode()).hexdigest(),
        "settings": {"kind": "legs", "tolerance": float(tolerance), "pnl": pnl, "periods_per_year": ppy},
    }
    problems = [c for c in checks if c["status"] in ("fail", "warn")]
    return to_jsonable({
        "schema": VERDICT_SCHEMA_ID, "verdict": verdict, "certificate_id": certificate_id(repro, verdict),
        "reasons": [f"{c['id']}: {c['summary']}" for c in problems],
        "checks": checks,
        "metrics": {
            "bars": int(rep.size), "periods_per_year": ppy, "reported_sharpe": sr_rep, "derived_sharpe": sr_der,
            "reported_total": float(rep.sum()), "derived_total": float(der.sum()), "unexplained_share": share,
        },
        "next_actions": [NEXT_ACTIONS[c["id"]] for c in checks if c["id"] in NEXT_ACTIONS and c["status"] in ("fail", "warn")],
        "reproducibility": repro, "scope": SCOPE_NOTE,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "disclaimer": DISCLAIMER,
    })


def write_fixed_returns(legs: str | Path | pd.DataFrame, path: str | Path, *, pnl: str = "log") -> Path:
    """Write the returns the legs really earn as ``date,return``: the corrected series, ready for ``verify --returns``."""
    body = legs if isinstance(legs, pd.DataFrame) and isinstance(legs.index, pd.DatetimeIndex) else load_legs(legs)
    fixed = pd.Series(rederive(body, pnl=pnl), index=body.index[1:], name="return")
    out = Path(path)
    out.write_text("date,return\n" + "".join(f"{d},{v:.10f}\n" for d, v in fixed.items()), encoding="utf-8")
    return out


__all__ = ["DEFAULT_TOLERANCE", "NEXT_ACTIONS", "SCOPE_NOTE", "load_legs", "rederive", "verify_legs", "write_fixed_returns"]
