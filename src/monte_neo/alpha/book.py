"""Family C: what does the strategy add to the fund's existing book?

Inputs are plain return series: the strategy ``r`` and a DataFrame ``book`` with one column per existing strategy (or a
single column with the total book), both indexed by date. A strategy with a high Sharpe on its own can still add
nothing when the fund already owns the same risk.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check

MIN_COMMON = 60
TAIL_SHARE = 0.10
MIN_GAIN = 0.05
BOOT_DRAWS = 500
BOOT_BLOCK = 10

NEXT_ACTIONS: dict[str, str] = {
    "book_correlation": "A high correlation with the book means the strategy repeats risk you own: size it as a replacement, not an addition.",
    "marginal_sharpe": "Adding it barely lifts the book's Sharpe: you already own this risk. Find a source of return the book lacks, or skip it.",
    "residual_vs_book": "After removing the book's exposure nothing significant is left: the return is the book's, relabelled.",
    "drawdown_overlap": "It loses when your book loses: do not count it as a hedge, and size it for the book's worst bars.",
}


def align_book(r: pd.Series, book: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, pd.Index]:
    """Align the strategy to the book by date.

    Args:
        r: Strategy returns indexed by date.
        book: Book returns, one column per strategy.

    Returns:
        ``(r, book_matrix, index)`` on the common, NaN-free dates.

    Raises:
        ValueError: If fewer than 60 common rows remain.
    """
    frame = pd.concat([r.rename("__strategy__"), book], axis=1, join="inner").dropna()
    if len(frame) < MIN_COMMON:
        raise ValueError(f"only {len(frame)} common rows between strategy and book (need {MIN_COMMON})")
    return frame["__strategy__"].to_numpy(float), frame.drop(columns="__strategy__").to_numpy(float), frame.index


def _sharpe_ann(x: np.ndarray, ppy: float) -> float:
    sd = float(np.std(x, ddof=1))
    return float(np.mean(x) / sd * np.sqrt(ppy)) if sd > 0 else 0.0


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def book_correlation(r: np.ndarray, book: np.ndarray, names: list[str]) -> dict[str, Any]:
    """C1: correlation with the book total, with each column, and in the book's worst 10 % of bars."""
    total = book.sum(axis=1)
    tail = total <= np.quantile(total, TAIL_SHARE)
    corr_total = _corr(r, total)
    tail_corr = _corr(r[tail], total[tail])
    per_col = {n: _corr(r, book[:, i]) for i, n in enumerate(names)}
    summary = f"correlation with the book {corr_total:.2f}; in the book's worst {int(TAIL_SHARE * 100)}% of bars {tail_corr:.2f}"
    details = {"corr_total": corr_total, "tail_corr": tail_corr, "tail_bars": int(tail.sum()), "per_column": per_col}
    return check("book_correlation", "statistics", "info", summary, details)


def _tangency_sharpe(r: np.ndarray, b: np.ndarray, ppy: float, ridge: float = 0.01) -> tuple[float, float]:
    """(book Sharpe, combined Sharpe) with ridge-regularised two-asset tangency weights."""
    x = np.column_stack([b, r])
    mu = x.mean(axis=0)
    cov = np.cov(x.T)
    w = np.linalg.solve(cov + ridge * np.mean(np.diag(cov)) * np.eye(2), mu)
    return _sharpe_ann(b, ppy), _sharpe_ann(x @ w, ppy)


def _boot_gain(r: np.ndarray, b: np.ndarray, ppy: float, seed: int) -> np.ndarray:
    """Seeded circular block bootstrap of the Sharpe gain (vectorised over draws)."""
    n = len(r)
    rng = np.random.default_rng(seed)
    nb = -(-n // BOOT_BLOCK)
    starts = rng.integers(0, n, size=(BOOT_DRAWS, nb))
    idx = ((starts[:, :, None] + np.arange(BOOT_BLOCK)) % n).reshape(BOOT_DRAWS, -1)[:, :n]
    rs, bs = r[idx], b[idx]
    mr, mb = rs.mean(1), bs.mean(1)
    vr, vb = rs.var(1, ddof=1), bs.var(1, ddof=1)
    cv = ((rs - mr[:, None]) * (bs - mb[:, None])).sum(1) / (n - 1)
    lam = 0.01 * (vr + vb) / 2
    a, d = vb + lam, vr + lam  # solve [[a, cv], [cv, d]] w = [mb, mr]
    det = a * d - cv * cv
    wb, wr = (d * mb - cv * mr) / det, (a * mr - cv * mb) / det
    comb = wb[:, None] * bs + wr[:, None] * rs
    k = np.sqrt(ppy)
    sd_c = comb.std(1, ddof=1)
    sr_c = np.divide(comb.mean(1), sd_c, out=np.zeros(BOOT_DRAWS), where=sd_c > 0) * k
    sr_b = np.divide(mb, np.sqrt(vb), out=np.zeros(BOOT_DRAWS), where=vb > 0) * k
    return sr_c - sr_b


def marginal_sharpe(r: np.ndarray, book: np.ndarray, ppy: float, seed: int = 0) -> dict[str, Any]:
    """C2: Sharpe of the book alone vs the book plus the strategy at its optimal weight.

    Warns when the gain is at most 0.05 or its 90 % block-bootstrap interval includes zero.
    """
    b = book.sum(axis=1)
    sr_book, sr_comb = _tangency_sharpe(r, b, ppy)
    gain = sr_comb - sr_book
    lo, hi = (float(v) for v in np.percentile(_boot_gain(r, b, ppy, seed), [5, 95]))
    alone = _sharpe_ann(r, ppy)
    details = {"sharpe_alone": alone, "sharpe_book": sr_book, "sharpe_combined": sr_comb, "gain": gain, "gain_ci90": [lo, hi]}
    if gain <= MIN_GAIN or lo <= 0 <= hi:
        s = f"on its own Sharpe {alone:.2f}; for your book {gain:+.2f} (90% interval {lo:+.2f}..{hi:+.2f}): you already own this"
        return check("marginal_sharpe", "statistics", "warn", s, details)
    s = f"on its own Sharpe {alone:.2f}; for your book {gain:+.2f} (90% interval {lo:+.2f}..{hi:+.2f})"
    return check("marginal_sharpe", "statistics", "pass", s, details)


def residual_vs_book(r: np.ndarray, book: np.ndarray) -> dict[str, Any]:
    """C3: OLS of the strategy on the book columns; Newey-West t of the intercept (warn if t < 2)."""
    n = len(r)
    x = np.column_stack([np.ones(n), book])
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta = xtx_inv @ x.T @ r
    e = r - x @ beta
    u = x * e[:, None]
    lag = int(4 * (n / 100.0) ** (2 / 9))
    s = u.T @ u
    for k in range(1, lag + 1):
        g = u[k:].T @ u[:-k]
        s += (1 - k / (lag + 1.0)) * (g + g.T)
    se = float(np.sqrt(max((xtx_inv @ s @ xtx_inv)[0, 0], 0.0)))
    t = float(beta[0] / se) if se > 0 else float("nan")
    details = {"alpha_per_bar": float(beta[0]), "t_alpha": t, "betas": [float(v) for v in beta[1:]], "r2": float(1 - e.var() / r.var()) if r.var() > 0 else 0.0}
    status = "pass" if t >= 2.0 else "warn"
    return check("residual_vs_book", "statistics", status, f"after the book's exposure the intercept has t = {t:.2f}", details)


def drawdown_overlap(r: np.ndarray, book: np.ndarray) -> dict[str, Any]:
    """C5: strategy mean return in the book's worst 10 % of bars vs overall (warn if it loses > 2x its average gain)."""
    total = book.sum(axis=1)
    tail = total <= np.quantile(total, TAIL_SHARE)
    in_tail, overall = float(r[tail].mean()), float(r.mean())
    details = {"mean_in_book_worst": in_tail, "mean_overall": overall, "tail_bars": int(tail.sum())}
    s = f"mean return {in_tail:.5f} in the book's worst bars vs {overall:.5f} overall"
    if overall > 0 and in_tail < 0 and -in_tail > 2 * overall:
        return check("drawdown_overlap", "statistics", "warn", s + ": it falls when your book falls", details)
    return check("drawdown_overlap", "statistics", "pass", s, details)


def run_book(r: pd.Series, book: pd.DataFrame, ppy: float, seed: int = 0) -> list[dict[str, Any]]:
    """Run family C (C1, C2, C3, C5).

    Args:
        r: Strategy returns indexed by date.
        book: Existing strategies' returns (columns) or the total book (one column).
        ppy: Periods per year.
        seed: Bootstrap seed.

    Returns:
        Check rows (category ``statistics``), or one skip row if the overlap is too short.
    """
    try:
        ra, ba, _ = align_book(r, book)
    except ValueError as exc:
        return [check("book_correlation", "statistics", "skip", str(exc), {})]
    return [
        book_correlation(ra, ba, [str(c) for c in book.columns]),
        marginal_sharpe(ra, ba, ppy, seed),
        residual_vs_book(ra, ba),
        drawdown_overlap(ra, ba),
    ]


__all__ = ["NEXT_ACTIONS", "align_book", "book_correlation", "drawdown_overlap", "marginal_sharpe", "residual_vs_book", "run_book"]
