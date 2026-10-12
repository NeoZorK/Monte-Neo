"""Family H, "after launch": does the live (or paper) strategy behave like its backtest, and is the alpha dead?

``verify_live`` compares live returns with the backtest returns of a certificate (or a returns file), reads fills
for implementation shortfall, and runs sequential tests for a dead edge. It reports; it never trades.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo import disclaimer
from monte_neo.verify.checks import check
from monte_neo.verify.live_seq import alpha_death_monitor, live_track_needed
from monte_neo.verify.recheck import load_certificate
from monte_neo.verify.returns_dd import load_returns
from monte_neo.verify.stats import infer_periods_per_year

SCHEMA = "live-monitor/1"
MIN_OVERLAP = 20
MIN_CORR = 0.5
SHORTFALL_RATIO = 1.5
FILL_COLUMNS = ("timestamp", "symbol", "side", "quantity", "price")


def _read(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    return pd.read_parquet(p) if p.suffix.lower() in (".parquet", ".pq") else pd.read_csv(p)


def load_live(source: str | Path | pd.DataFrame | pd.Series) -> dict[str, Any]:
    """Read live data: a returns file (date, return) or a fills file, detected by its columns.

    Fills need ``timestamp, symbol, side, quantity, price`` and may carry ``fee`` and ``reference_price`` (the
    decision or arrival price). Returns files follow ``load_returns`` (at least 24 observations).

    Returns:
        ``{"kind": "returns" | "fills", "returns": Series | None, "fills": DataFrame | None}``.

    Raises:
        ValueError: A fills file with missing columns, or an unreadable returns file.
    """
    if isinstance(source, pd.Series):
        return {"kind": "returns", "returns": load_returns(source), "fills": None}
    df = source.copy() if isinstance(source, pd.DataFrame) else _read(source)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "price" in df.columns and ("side" in df.columns or "quantity" in df.columns):
        missing = [c for c in FILL_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"fills file lacks columns: {', '.join(missing)}")
        return {"kind": "fills", "returns": None, "fills": df}
    return {"kind": "returns", "returns": load_returns(df, percent=False), "fills": None}


def _naive(index: Any) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(index, utc=True, errors="coerce"))
    return idx.tz_localize(None)


def backtest_returns_from_certificate(cert: dict[str, Any]) -> pd.Series:
    """Backtest step returns from the certificate's ``series`` section (equity at up to 400 sampled bars).

    Each value is the return between two sampled bars; the number of bars in each step is kept in ``Series.attrs["bars"]``.

    Raises:
        ValueError: The certificate has no usable equity series with timestamps.
    """
    s = cert.get("series") or {}
    eq, times, bars = s.get("equity"), s.get("time"), s.get("bar")
    if not eq or not times or len(eq) < 3:
        raise ValueError("the certificate has no equity series with timestamps; pass a backtest returns file instead")
    e = np.asarray(eq, dtype=np.float64)
    rets = e[1:] / np.where(e[:-1] > 0.0, e[:-1], np.nan) - 1.0
    out = pd.Series(rets, index=_naive(times[1:]), name="return").dropna()
    steps = np.diff(np.asarray(bars if bars else range(len(eq)), dtype=np.float64))
    out.attrs["bars"] = [float(max(b, 1.0)) for b in steps[-len(out):]] if len(out) else []
    return out


def _expectation(bt: pd.Series) -> dict[str, float]:
    """Per-bar mean, std, skew and kurtosis of the backtest (steps of several bars are scaled down)."""
    bars = np.asarray(bt.attrs.get("bars") or np.ones(len(bt)), dtype=np.float64)
    r = bt.to_numpy(dtype=np.float64)
    per_bar = r / bars
    z = r / np.sqrt(bars)
    sd = float(np.std(z, ddof=1)) if z.size > 1 else 0.0
    zc = (z - z.mean()) / sd if sd > 0.0 else np.zeros_like(z)
    return {"mean": float(per_bar.mean()), "std": sd, "skew": float(np.mean(zc**3)), "kurt": float(np.mean(zc**4)) if sd > 0 else 3.0}


def _align(bt: pd.Series, live: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Backtest and live returns on common dates; live is compounded into coarser backtest steps."""
    bi, li = _naive(bt.index), _naive(live.index)
    bt, live = pd.Series(bt.to_numpy(), index=bi), pd.Series(live.to_numpy(), index=li)
    if len(bt) > 2 and len(live) > 2 and np.median(np.diff(bi.asi8)) > 1.5 * np.median(np.diff(li.asi8)):
        bins = np.searchsorted(bi.asi8, li.asi8, side="left")
        grown = (1.0 + live).groupby(bins).prod() - 1.0
        grown = grown[(grown.index > 0) & (grown.index < len(bt))]
        live = pd.Series(grown.to_numpy(), index=bi[grown.index.to_numpy()])
    both = bt.index.intersection(live.index)
    return bt.loc[both], live.loc[both]


def _nw_mean_t(d: np.ndarray) -> float:
    """t statistic of the mean with a Newey-West (Bartlett) long-run variance."""
    n = d.size
    u = d - d.mean()
    lags = int(math.floor(4 * (n / 100.0) ** (2 / 9)))
    lrv = float(u @ u) / n
    for k in range(1, lags + 1):
        lrv += 2.0 * (1.0 - k / (lags + 1)) * float(u[k:] @ u[:-k]) / n
    return float(d.mean() / math.sqrt(max(lrv, 1e-30) / n))


def live_vs_backtest(bt: pd.Series, live: pd.Series, ppy: float) -> dict[str, Any]:
    """``live_vs_backtest`` (statistics): correlation, tracking error and mean difference on common dates."""
    b, v = _align(bt, live)
    if len(b) < MIN_OVERLAP:
        return check("live_vs_backtest", "statistics", "skip", f"live vs backtest: only {len(b)} overlapping periods (need {MIN_OVERLAP})")
    d = v.to_numpy() - b.to_numpy()
    corr = float(np.corrcoef(b.to_numpy(), v.to_numpy())[0, 1]) if b.std() > 0 and v.std() > 0 else 0.0
    t = _nw_mean_t(d)
    te = float(np.std(d, ddof=1) * math.sqrt(ppy))
    details = {"n_overlap": len(b), "correlation": corr, "tracking_error_annualized": te, "mean_difference": float(d.mean()), "nw_t": t, "min_correlation": MIN_CORR}
    problems = [m for ok, m in ((corr < MIN_CORR, f"correlation {corr:.2f} < {MIN_CORR}"), (t <= -2.0, f"live trails the backtest (Newey-West t {t:.1f})")) if ok]
    text = f"correlation {corr:.2f}, tracking error {te:.1%}, mean difference {d.mean():.5f} per period (t {t:.1f})"
    return check("live_vs_backtest", "statistics", "warn" if problems else "pass", (("; ".join(problems) + ": ") if problems else "") + text, details)


def implementation_shortfall(fills: pd.DataFrame | None, modelled_bps: float | None) -> dict[str, Any]:
    """``implementation_shortfall`` (economics): realised slippage in bps against the arrival price, versus the model."""
    if fills is None or "reference_price" not in fills.columns:
        return check("implementation_shortfall", "economics", "skip", "implementation shortfall: needs fills with reference_price")
    side = fills["side"].astype(str).str.lower().map({"buy": 1.0, "b": 1.0, "long": 1.0, "sell": -1.0, "s": -1.0, "short": -1.0})
    ref = pd.to_numeric(fills["reference_price"], errors="coerce")
    px = pd.to_numeric(fills["price"], errors="coerce")
    bps = (side * (px - ref) / ref * 1e4).replace([np.inf, -np.inf], np.nan).dropna()
    if bps.empty:
        return check("implementation_shortfall", "economics", "skip", "implementation shortfall: no usable fills (side, price, reference_price)")
    mean, p95 = float(bps.mean()), float(np.percentile(bps, 95))
    details: dict[str, Any] = {"n_fills": int(bps.size), "mean_bps": mean, "p95_bps": p95, "modelled_slippage_bps": modelled_bps, "ratio_limit": SHORTFALL_RATIO}
    if modelled_bps is None:
        return check("implementation_shortfall", "economics", "info", f"realised slippage {mean:.2f} bps (p95 {p95:.2f}); no modelled value to compare", details)
    if mean > SHORTFALL_RATIO * modelled_bps and mean > 0.0:
        details["recommended_slippage_bps"] = round(math.ceil(mean * 2.0) / 2.0, 1)
        return check("implementation_shortfall", "economics", "warn", f"realised slippage {mean:.2f} bps is above {SHORTFALL_RATIO}x the modelled {modelled_bps:.2f} bps (p95 {p95:.2f}); use slippage_bps={details['recommended_slippage_bps']}", details)
    return check("implementation_shortfall", "economics", "pass", f"realised slippage {mean:.2f} bps (p95 {p95:.2f}) within {SHORTFALL_RATIO}x of the modelled {modelled_bps:.2f} bps", details)


_ACTIONS = {
    "live_vs_backtest": "Live differs from the backtest: compare fills, data and timing with the backtest; fix the mismatch before judging the strategy.",
    "implementation_shortfall": "Execution costs more than modelled: re-run verify with the recommended slippage_bps and trade less or in smaller size.",
    "alpha_death_monitor": "Sequential tests say the edge may be gone: reduce size or pause, and review the strategy against the certificate.",
}


def verify_live(
    certificate_or_backtest: dict[str, Any] | str | Path | pd.Series,
    live: dict[str, Any] | str | Path | pd.DataFrame | pd.Series,
    *,
    fills: str | Path | pd.DataFrame | None = None,
    modelled_slippage_bps: float | None = None,
    haircut: float = 0.5,
) -> dict[str, Any]:
    """Compare live (or paper) results with the backtest.

    Args:
        certificate_or_backtest: A ``strategy-verdict/1`` certificate (dict or JSON path), a backtest returns file,
            or a returns Series.
        live: Live returns or fills (a path, frame, Series or the result of ``load_live``).
        fills: Optional fills with ``reference_price`` when ``live`` holds returns.
        modelled_slippage_bps: The model's slippage; default from the certificate.
        haircut: Share of the backtest mean return expected live (default 0.5).

    Returns:
        A ``live-monitor/1`` report: status (ok / warn), checks, metrics, next_actions, generated_at, disclaimer.
    """
    src = certificate_or_backtest
    cert = load_certificate(src) if isinstance(src, dict) or (isinstance(src, (str, Path)) and str(src).endswith(".json")) else None
    bt = backtest_returns_from_certificate(cert) if cert else load_returns(src)
    if modelled_slippage_bps is None and cert:
        modelled_slippage_bps = ((cert.get("reproducibility") or {}).get("model") or {}).get("slippage_bps")
    data = live if isinstance(live, dict) and "kind" in live else load_live(live)
    fill_df = data["fills"] if data["kind"] == "fills" else (load_live(fills)["fills"] if fills is not None else None)
    expect = _expectation(bt)
    rows: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {"haircut": haircut, "backtest_mean_per_bar": expect["mean"], "modelled_slippage_bps": modelled_slippage_bps}
    if data["returns"] is not None:
        r = data["returns"]
        ppy = infer_periods_per_year(r.index)
        metrics.update(live_bars=len(r), live_sharpe_annualized=float(r.mean() / r.std(ddof=1) * math.sqrt(ppy)) if r.std() > 0 else 0.0)
        rows += [live_vs_backtest(bt, r, ppy), alpha_death_monitor(r, expect, haircut), live_track_needed(len(r), expect, haircut)]
    rows.append(implementation_shortfall(fill_df, modelled_slippage_bps))
    warned = [c for c in rows if c["status"] == "warn"]
    return {
        "schema": SCHEMA, "status": "warn" if warned else "ok", "checks": rows, "metrics": metrics,
        "next_actions": [_ACTIONS[c["id"]] for c in warned if c["id"] in _ACTIONS],
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "disclaimer": disclaimer.SHORT,
    }


__all__ = ["backtest_returns_from_certificate", "implementation_shortfall", "live_vs_backtest", "load_live", "verify_live"]
