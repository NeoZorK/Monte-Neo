"""``model_cutoff``: did a language or foundation model trade a past it remembered?

A strategy that asks an LLM (or a pre-trained time-series model) for a view on a date the model was trained on can
"predict" news and prices it has already read. No code probe sees this: the leak is in the model's weights. The test
is in time: the edge must survive the date the model's training data ends. The check compares the strategy's Sharpe
before and after that date with a block bootstrap, next to buy-and-hold on the same dates (a market that simply turned
is not a leak).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from monte_neo.verify.checks import check

MIN_BARS = 30
DRAWS = 500
BLOCK = 10


def _sharpe(r: np.ndarray, ppy: float) -> float:
    sd = float(np.std(r, ddof=1)) if r.size > 1 else 0.0
    return float(np.mean(r) / sd * np.sqrt(ppy)) if sd > 0 else 0.0


def _boot_sharpes(r: np.ndarray, ppy: float, rng: np.random.Generator) -> np.ndarray:
    """Annualised Sharpe of DRAWS circular block-bootstrap resamples of ``r`` (vectorised)."""
    n = r.size
    blocks = -(-n // BLOCK)
    starts = rng.integers(0, n, size=(DRAWS, blocks))
    idx = (starts[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(DRAWS, -1)[:, :n] % n
    sample = r[idx]
    sd = sample.std(axis=1, ddof=1)
    return np.where(sd > 0, sample.mean(axis=1) / np.where(sd > 0, sd, 1.0) * np.sqrt(ppy), 0.0)


def parse_cutoff(value: str) -> pd.Timestamp:
    """``YYYY-MM`` (the first day of that month) or ``YYYY-MM-DD`` as a naive UTC timestamp."""
    try:
        stamp = pd.Timestamp(value + "-01" if len(value) == 7 else value)
    except ValueError as exc:
        raise ValueError(f"model cutoff must be YYYY-MM or YYYY-MM-DD, got {value!r}") from exc
    return stamp.tz_convert("UTC").tz_localize(None) if stamp.tzinfo else stamp


def cutoff_row(
    rets: np.ndarray, stamps: Any, cutoff: str, ppy: float, bench_rets: np.ndarray | None = None, seed: int = 0
) -> dict[str, Any]:
    """Check row ``model_cutoff`` (category ``lookahead``).

    Args:
        rets: Per-bar strategy returns after costs.
        stamps: Timestamps of those bars (same length).
        cutoff: Training-data cutoff of the model the strategy uses (``YYYY-MM`` or ``YYYY-MM-DD``).
        ppy: Bars per year, for annualising.
        bench_rets: Per-bar buy-and-hold returns on the same bars (context), optional.
        seed: Bootstrap seed.

    Returns:
        ``fail`` when the edge exists before the cutoff and is gone after it (significant drop, Sharpe after <= 0),
        ``warn`` for a significant drop to less than half, ``pass`` otherwise, ``skip`` with too few bars on a side.
    """
    when = parse_cutoff(cutoff)
    times = pd.DatetimeIndex(pd.to_datetime(stamps, utc=True)).tz_localize(None)
    r = np.nan_to_num(np.asarray(rets, dtype=np.float64))
    before = np.asarray(times < when)
    pre, post = r[before], r[~before]
    details: dict[str, Any] = {"cutoff": when.date().isoformat(), "bars_before": int(pre.size), "bars_after": int(post.size)}
    if pre.size < MIN_BARS or post.size < MIN_BARS:
        return check(
            "model_cutoff", "lookahead", "skip",
            f"need {MIN_BARS} bars on each side of the model cutoff {details['cutoff']}: {pre.size} before, {post.size} after",
            details,
        )
    rng = np.random.default_rng(seed)
    s_pre, s_post = _sharpe(pre, ppy), _sharpe(post, ppy)
    diff = _boot_sharpes(pre, ppy, rng) - _boot_sharpes(post, ppy, rng)
    p_value = float(np.mean(diff <= 0.0))
    details.update(sharpe_before=s_pre, sharpe_after=s_post, p_value_drop=p_value)
    if bench_rets is not None:
        b = np.nan_to_num(np.asarray(bench_rets, dtype=np.float64))
        details.update(benchmark_sharpe_before=_sharpe(b[before], ppy), benchmark_sharpe_after=_sharpe(b[~before], ppy))
    text = f"Sharpe {s_pre:.2f} before the model cutoff {details['cutoff']}, {s_post:.2f} after (p {p_value:.3f})"
    if p_value < 0.05 and s_pre > 0.5 and s_post <= 0.0:
        return check("model_cutoff", "lookahead", "fail", f"{text}: the edge exists only where the model may have seen the answers", details)
    if p_value < 0.10 and s_post < 0.5 * s_pre:
        return check("model_cutoff", "lookahead", "warn", f"{text}: most of the edge is in the period the model was trained on", details)
    return check("model_cutoff", "lookahead", "pass", f"{text}: the edge survives the cutoff", details)


__all__ = ["cutoff_row", "parse_cutoff"]
