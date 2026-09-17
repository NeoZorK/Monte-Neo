"""Holdout / train-test helper around research export (anti-overfit, no ML).

Schema: ``mn.holdout_report.v1``.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from monte_neo.backtest.batch import run_bar_backtest_batch
from monte_neo.backtest.export import EXPORT_API_VERSION, export_sma_sweep
from monte_neo.backtest.model import ExecutionModel
from monte_neo.backtest.signal_factory import build_sma_cross_grid

HOLDOUT_SCHEMA = "mn.holdout_report.v1"


def split_bar_range(
    n_bars: int,
    *,
    train_frac: float = 0.7,
    min_holdout: int = 100,
    min_train: int = 200,
) -> tuple[slice, slice]:
    """Return ``(train_slice, holdout_slice)`` for contiguous bar indices."""
    n = int(n_bars)
    if n < min_train + min_holdout:
        raise ValueError(
            f"need at least {min_train + min_holdout} bars for holdout split, got {n}"
        )
    if not (0.05 < float(train_frac) < 0.95):
        raise ValueError("train_frac must be in (0.05, 0.95)")
    cut = int(round(n * float(train_frac)))
    cut = max(min_train, min(cut, n - min_holdout))
    return slice(0, cut), slice(cut, n)


def _slice_ohlcv(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    sl: slice,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.asarray(open_)[sl],
        np.asarray(high)[sl],
        np.asarray(low)[sl],
        np.asarray(close)[sl],
    )


def _pairs_returns(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    pairs: list[tuple[int, int]],
    *,
    model: ExecutionModel,
    device: str,
) -> dict[str, Any]:
    """Evaluate fixed (fast, slow) pairs on one window via signal grid + batch."""
    c = np.asarray(close, dtype=np.float64)
    sig = build_sma_cross_grid(c, pairs, device="cpu_numba")
    batch = run_bar_backtest_batch(
        open_, high, low, close, sig["signals"], model=model, device=device
    )
    rets = np.asarray(batch["total_returns"], dtype=np.float64)
    rows = [
        {"fast": int(f), "slow": int(s), "total_return": float(rets[i])}
        for i, (f, s) in enumerate(pairs)
    ]
    return {
        "device": batch.get("device", device),
        "fallback_reason": batch.get("fallback_reason"),
        "rows": rows,
        "elapsed_s": float(sig.get("elapsed_s") or 0.0) + float(batch.get("elapsed_s") or 0.0),
    }


def holdout_sma_sweep(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    *,
    combos: int = 64,
    train_frac: float = 0.7,
    top_k: int = 5,
    model: ExecutionModel | None = None,
    device: str = "auto",
    min_holdout: int = 100,
    gap_high: float = 0.15,
    gap_med: float = 0.05,
    promote_mode: str = "holdout_positive",
) -> dict[str, Any]:
    """Train SMA sweep on the first window; score top-K pairs on holdout.

    Practical anti-overfit without ML.

    ``promote_mode``:
      - ``holdout_positive`` (default): promote if train and holdout returns > 0.
        Large gaps still raise ``overfit_risk`` / suggest MC, but do **not** block.
      - ``strict``: also require ``overfit_risk != "high"`` (legacy / conservative).
    """
    model = model or ExecutionModel(side_mode="long_flat")
    n = int(np.asarray(close).shape[0])
    train_sl, hold_sl = split_bar_range(n, train_frac=train_frac, min_holdout=min_holdout)
    o_tr, h_tr, l_tr, c_tr = _slice_ohlcv(open_, high, low, close, train_sl)
    o_ho, h_ho, l_ho, c_ho = _slice_ohlcv(open_, high, low, close, hold_sl)

    t0 = time.perf_counter()
    train = export_sma_sweep(
        o_tr, h_tr, l_tr, c_tr, combos=combos, model=model, device=device
    )
    rows = list((train.get("metrics") or {}).get("rows") or [])
    if not rows:
        raise RuntimeError("train sweep produced no rows")
    ranked = sorted(rows, key=lambda r: float(r.get("total_return", 0.0)), reverse=True)
    k = max(1, min(int(top_k), len(ranked)))
    top = ranked[:k]
    pairs = [(int(r["fast"]), int(r["slow"])) for r in top]

    hold = _pairs_returns(o_ho, h_ho, l_ho, c_ho, pairs, model=model, device=device)
    hold_by = {(r["fast"], r["slow"]): float(r["total_return"]) for r in hold["rows"]}

    train_best = float(top[0]["total_return"])
    best_pair = (int(top[0]["fast"]), int(top[0]["slow"]))
    holdout_at_best = hold_by[best_pair]
    gap_best = train_best - holdout_at_best

    paired = []
    gaps = []
    for r in top:
        key = (int(r["fast"]), int(r["slow"]))
        tr = float(r["total_return"])
        ho = hold_by[key]
        g = tr - ho
        gaps.append(g)
        paired.append(
            {
                "fast": key[0],
                "slow": key[1],
                "train_return": tr,
                "holdout_return": ho,
                "gap": g,
            }
        )

    mean_gap = float(np.mean(gaps)) if gaps else 0.0
    if gap_best >= gap_high or mean_gap >= gap_high:
        overfit = "high"
    elif gap_best >= gap_med or mean_gap >= gap_med:
        overfit = "med"
    else:
        overfit = "low"

    mode = str(promote_mode or "holdout_positive").strip().lower()
    if mode not in {"holdout_positive", "strict"}:
        raise ValueError("promote_mode must be 'holdout_positive' or 'strict'")

    base_ok = holdout_at_best > 0.0 and train_best > 0.0
    if mode == "strict":
        promote_ok = base_ok and overfit != "high"
    else:
        promote_ok = base_ok

    if promote_ok:
        next_action = "promote_paper_oms"
    elif holdout_at_best <= 0.0 and train_best > 0.0:
        next_action = "reject" if overfit == "high" else "stop"
    elif overfit == "high" and train_best > 0.0:
        next_action = "run_mc"
    else:
        next_action = "stop"

    reasons: list[str] = [
        f"train bars [{train_sl.start}:{train_sl.stop}] holdout [{hold_sl.start}:{hold_sl.stop}]",
        f"train_best={train_best:.4f} holdout_at_best={holdout_at_best:.4f} gap={gap_best:.4f}",
        f"mean_gap_top_{k}={mean_gap:.4f} overfit_risk={overfit} promote_mode={mode}",
    ]
    if promote_ok and overfit == "high":
        reasons.append("promote allowed (holdout>0) but gap high — prefer MC before size-up")
    if not promote_ok:
        reasons.append("promote blocked: non-positive train/holdout" + (" or strict overfit" if mode == "strict" else ""))

    elapsed = time.perf_counter() - t0
    return {
        "schema": HOLDOUT_SCHEMA,
        "ok": bool(train.get("ok", True)),
        "export_api_version": EXPORT_API_VERSION,
        "lane": "research_bar",
        "engine": "monte_neo.backtest.holdout_sma_sweep",
        "model": model.to_dict(),
        "split": {
            "train_frac": float(train_frac),
            "train_bars": int(train_sl.stop - train_sl.start),
            "holdout_bars": int(hold_sl.stop - hold_sl.start),
            "train_slice": [train_sl.start, train_sl.stop],
            "holdout_slice": [hold_sl.start, hold_sl.stop],
            "n_bars": n,
        },
        "train": {
            "device": train.get("device"),
            "fallback_reason": train.get("fallback_reason"),
            "combos": train.get("combos"),
            "best_return": train_best,
            "best_pair": {"fast": best_pair[0], "slow": best_pair[1]},
            "timing": train.get("timing"),
        },
        "holdout": {
            "device": hold.get("device"),
            "fallback_reason": hold.get("fallback_reason"),
            "at_train_best": holdout_at_best,
            "top_k": paired,
        },
        "metrics": {
            "gap_best": float(gap_best),
            "mean_gap_top_k": mean_gap,
            "overfit_risk": overfit,
            "promote_mode": mode,
            "promote_ok": promote_ok,
            "next_action": next_action,
            "worth_mc_stress": bool(overfit == "high" or (promote_ok and gap_best >= gap_med)),
        },
        "reasons": reasons,
        "timing": {"elapsed_s": float(elapsed), "includes_signal_build": True},
    }


def holdout_to_research_metrics(report: dict[str, Any]) -> dict[str, Any]:
    """Compact metrics for :func:`monte_neo.policy.build_research_state` enrichment."""
    m = dict(report.get("metrics") or {})
    return {
        "holdout_gap": m.get("gap_best"),
        "holdout_mean_gap": m.get("mean_gap_top_k"),
        "holdout_return": (report.get("holdout") or {}).get("at_train_best"),
        "holdout_overfit_risk": m.get("overfit_risk"),
        "holdout_promote_ok": m.get("promote_ok"),
    }


__all__ = [
    "HOLDOUT_SCHEMA",
    "holdout_sma_sweep",
    "holdout_to_research_metrics",
    "split_bar_range",
]
