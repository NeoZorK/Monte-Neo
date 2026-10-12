"""Allocator due diligence on a return series only: no code, no positions, just the track record."""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monte_neo._version import __version__
from monte_neo.verify import returns_dd_checks as rc
from monte_neo.verify.checks import check
from monte_neo.verify.claim import claim_row, parse_claim
from monte_neo.verify.schema import DISCLAIMER, VERDICT_SCHEMA_ID, aggregate_verdict, to_jsonable
from monte_neo.verify.stats import infer_periods_per_year
from monte_neo.verify.verdict import certificate_id

MIN_OBS = 24
SCOPE_NOTE = (
    "Return series only: smoothing, distribution and significance were checked; look-ahead, costs and data quality "
    "behind the returns cannot be checked without the strategy or positions."
)
NEXT_ACTIONS: dict[str, str] = {
    "return_smoothing": "Ask for the valuation policy and the share of illiquid or model-priced positions; judge the manager on the unsmoothed Sharpe, not the reported one.",
    "zero_kink": "Ask for daily or position-level data around small losing months: losses may be deferred, netted or rounded up.",
    "implausible_consistency": "A record this smooth is rarely real: demand an independent administrator's statements and a position-level audit before any allocation.",
    "round_numbers": "Ask for the administrator's statements: returns that are round numbers may be typed or estimated, not computed from NAV.",
    "track_record_significance": "The record is too short or too weak for the number of strategies run: wait for more history, or ask for the returns of every fund and strategy the manager launched, including closed ones.",
    "drawdown_consistency": "Drawdown is too shallow for the volatility: ask whether marks are smoothed and whether losing periods were left out or re-based.",
    "claim_consistency": "The claimed numbers are better than the series reproduces: use the verified Sharpe, return and drawdown.",
    "returns_only_scope": "To check look-ahead, costs and data quality, ask for the strategy code or the position history and run the full verify.",
}


def _clean(s: pd.Series) -> pd.Series:
    idx = pd.DatetimeIndex(pd.to_datetime(s.index, errors="coerce"))
    if idx.isna().any():
        raise ValueError(f"{int(idx.isna().sum())} dates cannot be parsed; every return needs a date")
    if idx.duplicated().any():
        raise ValueError(f"{int(idx.duplicated().sum())} duplicate dates; keep one return per period")
    out = pd.Series(pd.to_numeric(s.to_numpy(), errors="coerce"), index=idx, name="return").sort_index()
    if out.isna().any():
        raise ValueError(f"{int(out.isna().sum())} returns are empty or not numbers")
    if not np.isfinite(out.to_numpy()).all():
        raise ValueError("returns contain infinite values")
    return out


def load_returns(path_or_df: str | Path | pd.DataFrame | pd.Series, column: str | None = None, *, percent: bool | None = None) -> pd.Series:
    """Load a return series (date + return) from CSV, parquet, a DataFrame or a Series.

    Args:
        path_or_df: A CSV or parquet path, a DataFrame with a date column (or a datetime index), or a Series with a
            datetime index.
        column: Name of the return column; default is the first numeric non-date column.
        percent: ``True`` if values are percent, ``False`` if decimals, ``None`` to detect (|median| > 1 or std > 0.5
            reads as percent).

    Returns:
        Decimal returns indexed by date, sorted, named ``return``.

    Raises:
        ValueError: Missing dates, duplicate dates, unparseable values or fewer than 24 observations.
    """
    if isinstance(path_or_df, pd.Series):
        s = path_or_df
    else:
        if isinstance(path_or_df, pd.DataFrame):
            df = path_or_df
        else:
            p = Path(path_or_df)
            df = pd.read_parquet(p) if p.suffix.lower() in (".parquet", ".pq") else pd.read_csv(p)
        if isinstance(df.index, pd.DatetimeIndex):
            dates, body = df.index, df
        else:
            names = {str(c).lower(): c for c in df.columns}
            key = next((names[n] for n in ("date", "time", "timestamp", "datetime", "month", "period") if n in names), None)
            if key is None:
                raise ValueError("no date column found: add a column named date (or pass a DataFrame with a datetime index)")
            dates, body = pd.DatetimeIndex(pd.to_datetime(df[key], errors="coerce")), df.drop(columns=[key])
        if column is not None:
            if column not in body.columns:
                raise ValueError(f"column {column!r} not found; columns: {', '.join(map(str, body.columns))}")
            col = column
        else:
            num = [c for c in body.columns if pd.to_numeric(body[c], errors="coerce").notna().mean() > 0.9]
            if not num:
                raise ValueError("no numeric return column found")
            col = num[0]
        s = pd.Series(body[col].to_numpy(), index=dates)
    out = _clean(s)
    if out.size < MIN_OBS:
        raise ValueError(f"only {out.size} observations; at least {MIN_OBS} are needed (two years of monthly returns)")
    pct = bool(abs(float(out.median())) > 1.0 or float(out.std()) > 0.5) if percent is None else bool(percent)
    return out / 100.0 if pct else out


def _ppy(index: pd.DatetimeIndex, given: float | None) -> float:
    if given is not None:
        return float(given)
    raw = infer_periods_per_year(index, default=12.0)
    return next((float(c) for c in (4, 12, 52, 252, 365) if abs(raw - c) / c < 0.03), round(raw, 2))


def _nw_alpha_t(y: np.ndarray, x: np.ndarray) -> tuple[float, float, float]:
    n = y.size
    xm = np.column_stack([np.ones(n), x])
    beta = np.linalg.lstsq(xm, y, rcond=None)[0]
    e = y - xm @ beta
    lags = int(math.floor(4 * (n / 100.0) ** (2 / 9)))
    u = xm * e[:, None]
    s = u.T @ u
    for k in range(1, lags + 1):
        g = u[k:].T @ u[:-k]
        s += (1 - k / (lags + 1)) * (g + g.T)
    bread = np.linalg.inv(xm.T @ xm)
    cov = bread @ s @ bread
    return float(beta[0]), float(beta[1]), float(beta[0] / math.sqrt(max(cov[0, 0], 1e-30)))


def benchmark_relation(r: pd.Series, bench: pd.Series, ppy: float) -> dict[str, Any]:
    """Beta, correlation, Newey-West alpha t and up/down capture against a benchmark."""
    both = pd.concat([r, bench], axis=1, join="inner").dropna()
    if both.shape[0] < MIN_OBS:
        return check("benchmark_relation", "statistics", "skip", f"only {both.shape[0]} dates overlap the benchmark")
    y, x = both.iloc[:, 0].to_numpy(), both.iloc[:, 1].to_numpy()
    alpha, beta, t = _nw_alpha_t(y, x)
    up, dn = x > 0, x < 0
    cap_up = float(y[up].mean() / x[up].mean()) if up.any() else None
    cap_dn = float(y[dn].mean() / x[dn].mean()) if dn.any() else None
    corr = float(np.corrcoef(y, x)[0, 1])
    det = {"n": int(y.size), "beta": beta, "correlation": corr, "alpha_annual": alpha * ppy, "alpha_t_newey_west": t,
           "up_capture": cap_up, "down_capture": cap_dn}
    msg = f"beta {beta:.2f}, correlation {corr:.2f}, annual alpha {alpha * ppy:+.1%} (Newey-West t={t:.1f})"
    if cap_up is not None and cap_dn is not None:
        msg += f", up capture {cap_up:.0%}, down capture {cap_dn:.0%}"
    return check("benchmark_relation", "statistics", "info", msg, det)


def _hash(s: pd.Series | None) -> str | None:
    if s is None:
        return None
    return hashlib.sha256(s.rename("return").to_csv(date_format="%Y-%m-%d").encode()).hexdigest()


def _claim_values(claim: dict[str, Any], years: float) -> dict[str, Any]:
    """Turn an annual figure (``annual_return`` / ``cagr``) into a cumulative ``total_return`` over the record."""
    out = dict(claim)
    for key in ("annual_return", "cagr"):
        if key in out:
            raw = str(out.pop(key)).strip()
            annual = float(raw.rstrip("%")) / (100.0 if raw.endswith("%") else 1.0)
            out["total_return"] = (1.0 + annual) ** years - 1.0
    return out


def verify_returns(
    returns: pd.Series,
    *,
    benchmark: pd.Series | None = None,
    n_strategies: int = 1,
    claim: dict[str, Any] | None = None,
    periods_per_year: float | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Run the return-series red-flag checks and build a ``strategy-verdict/1`` report.

    Args:
        returns: Decimal returns indexed by date (see ``load_returns``).
        benchmark: Optional benchmark returns for ``benchmark_relation``.
        n_strategies: How many funds or strategies the manager ran (selection bias for the deflated Sharpe).
        claim: Optional claimed ``sharpe``, ``total_return`` (or ``annual_return``) and ``max_drawdown``.
        periods_per_year: Override the periods per year inferred from the dates.
        seed: Seed for the drawdown simulation.

    Returns:
        The report dict with checks, metrics, verdict and a reproducible ``certificate_id``.
    """
    if not isinstance(returns, pd.Series):  # a path or a table: read it like the CLI and MCP give it
        returns = load_returns(returns)
    if benchmark is not None and not isinstance(benchmark, pd.Series):
        benchmark = load_returns(benchmark)
    r = _clean(returns) if not isinstance(returns.index, pd.DatetimeIndex) else returns.sort_index()
    if r.size < MIN_OBS:
        raise ValueError(f"only {r.size} observations; at least {MIN_OBS} are needed")
    v = r.to_numpy(dtype=np.float64)
    ppy = _ppy(pd.DatetimeIndex(r.index), periods_per_year)
    n_str = max(1, int(n_strategies))
    sd = float(np.std(v, ddof=1))
    sharpe = float(v.mean() / sd * math.sqrt(ppy)) if sd > 0 else 0.0
    years = v.size / ppy
    total = float(np.prod(1.0 + v) - 1.0)
    cagr = float((1.0 + total) ** (1.0 / years) - 1.0) if total > -1 else -1.0
    dd = rc.max_drawdown(v)
    sig, sig_m = rc.track_record_significance(v, ppy, n_str)
    smooth = rc.return_smoothing(v, ppy)
    checks = [
        check("returns_only_scope", "integrity", "info", SCOPE_NOTE),
        smooth,
        rc.zero_kink(v),
        rc.implausible_consistency(v, ppy),
        rc.round_numbers(v),
        sig,
        rc.drawdown_consistency(v, seed),
    ]
    if benchmark is not None:
        checks.append(benchmark_relation(r, _clean(benchmark), ppy))
    claim_norm = None
    if claim:
        claim_norm = parse_claim(_claim_values(claim, years))
        checks.append(claim_row(claim_norm, {"sharpe": sharpe, "total_return": total, "max_drawdown": dd}))
    verdict = aggregate_verdict(checks)
    repro = {
        "engine": "monte-neo",
        "engine_version": __version__,
        "data_sha256": _hash(r),
        "n_trials": n_str,
        "settings": {"kind": "returns", "n_strategies": n_str, "periods_per_year": ppy, "seed": int(seed),
                     "claim": claim_norm, "benchmark_sha256": _hash(benchmark)},
    }
    metrics = {
        "n": int(v.size), "periods_per_year": ppy, "annual_return": cagr, "annual_vol": sd * math.sqrt(ppy),
        "sharpe": sharpe, "unsmoothed_sharpe": smooth["details"]["unsmoothed_sharpe"], "max_drawdown": dd,
        "psr": sig_m["psr"], "dsr": sig_m["dsr"],
    }
    problems = [c for c in checks if c["status"] in ("fail", "warn")]
    return to_jsonable({
        "schema": VERDICT_SCHEMA_ID,
        "verdict": verdict,
        "certificate_id": certificate_id(repro, verdict),
        "reasons": [f"{c['id']}: {c['summary']}" for c in problems],
        "checks": checks,
        "metrics": metrics,
        "next_actions": [NEXT_ACTIONS[c["id"]] for c in checks if c["id"] in NEXT_ACTIONS and (c["status"] in ("fail", "warn") or c["id"] == "returns_only_scope")],
        "reproducibility": repro,
        "scope": SCOPE_NOTE,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "disclaimer": DISCLAIMER,
    })


def recheck_returns(certificate: dict[str, Any], returns: pd.Series, *, benchmark: pd.Series | None = None) -> dict[str, Any]:
    """Re-run a returns certificate with its stored settings and compare the id.

    Args:
        certificate: A report made by ``verify_returns``.
        returns: The return series to test against the certificate.
        benchmark: The benchmark series, if the certificate used one.

    Returns:
        ``{"reproduced": bool, "certificate_id", "expected_id", "verdict", "data_matches"}``.
    """
    repro = certificate.get("reproducibility", {})
    st = repro.get("settings", {})
    fresh = verify_returns(returns, benchmark=benchmark, n_strategies=int(st.get("n_strategies", 1)),
                           claim=st.get("claim"), periods_per_year=st.get("periods_per_year"), seed=int(st.get("seed", 0)))
    return {
        "reproduced": fresh["certificate_id"] == certificate.get("certificate_id"),
        "certificate_id": fresh["certificate_id"],
        "expected_id": certificate.get("certificate_id"),
        "verdict": fresh["verdict"],
        "data_matches": fresh["reproducibility"]["data_sha256"] == repro.get("data_sha256"),
    }


def demo_returns(seed: int = 0) -> dict[str, pd.Series]:
    """Three monthly series 2015-2024: ``honest``, ``smoothed`` (MA 0.5/0.3/0.2 of an honest one) and ``too_good``."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2015-01-31", periods=120, freq="ME")
    honest = rng.normal(0.0070, 0.03, 120)
    raw = rng.normal(0.0085, 0.035, 122)
    smoothed = 0.5 * raw[2:] + 0.3 * raw[1:-1] + 0.2 * raw[:-2]
    good = rng.normal(0.010, 0.012, 120)
    lose = good < 0
    hide = lose & (rng.random(120) < 0.9)  # small losses rounded up to small gains
    good[hide] = rng.uniform(0.0, 0.0022, int(hide.sum()))
    return {"honest": pd.Series(honest, idx, name="return"), "smoothed": pd.Series(smoothed, idx, name="return"),
            "too_good": pd.Series(good, idx, name="return")}


__all__ = ["NEXT_ACTIONS", "SCOPE_NOTE", "demo_returns", "load_returns", "recheck_returns", "verify_returns"]
