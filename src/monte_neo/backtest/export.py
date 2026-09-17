"""Stable research-bar export surface for external honesty harnesses.

No peer product names. Schema is versioned via :data:`EXPORT_API_VERSION`.
Timers always disclose what work is included (signal build vs economics).
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from monte_neo._version import __version__
from monte_neo.backtest.bar_engine import run_bar_backtest
from monte_neo.backtest.batch import run_bar_backtest_batch
from monte_neo.backtest.golden import verify_golden_vectors
from monte_neo.backtest.memory_plan import plan_research_bytes
from monte_neo.backtest.model import ExecutionModel
from monte_neo.backtest.sweep import run_sma_sweep, sma_signal

EXPORT_API_VERSION = "1"

REQUIRED_WORK_KEYS: tuple[str, ...] = (
    "next_bar_fill",
    "fees",
    "slippage",
    "cash_position_equity",
)


def research_manifest() -> dict[str, Any]:
    """Machine-readable description of the research-bar lane export."""
    return {
        "export_api_version": EXPORT_API_VERSION,
        "package_version": __version__,
        "lane": "research_bar",
        "engine": "monte_neo.backtest",
        "semantics": {
            "fill_policy_default": "next_bar_open",
            "signal_on_bar_t_fills_on_t_plus_1": True,
            "costs": "commission_bps + slippage_bps (+ impact) on fill notional",
            "reference_dtype": "float64",
            "gpu_dtype_default": "float32",
            "parity_policy": "Numba float64 reference; Metal within documented atol",
        },
        "required_work_keys": list(REQUIRED_WORK_KEYS),
        "entrypoints": [
            "export_single",
            "export_batch",
            "export_sma_sweep",
            "verify_export_golden",
            "research_manifest",
            "plan_research_bytes",
            "build_sma_cross_grid",
            "holdout_sma_sweep",
            "split_bar_range",
        ],
    }


def _timing(*, elapsed_s: float, includes_signal_build: bool) -> dict[str, Any]:
    return {
        "elapsed_s": float(elapsed_s),
        "includes_signal_build": bool(includes_signal_build),
        "warmup_excluded": False,
    }


def export_single(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signal: np.ndarray,
    model: ExecutionModel | None = None,
    *,
    session_mask: np.ndarray | None = None,
    include_equity: bool = False,
    equity_stride: int = 1,
    include_journal: bool = False,
    memory_plan: bool = False,
) -> dict[str, Any]:
    """Single-path research run with stable export schema + wall timer.

    Signal arrays are caller-owned: ``includes_signal_build`` is False.
    """
    model = model or ExecutionModel()
    t0 = time.perf_counter()
    raw = run_bar_backtest(
        open_, high, low, close, signal, model=model, session_mask=session_mask
    )
    elapsed = time.perf_counter() - t0
    sess_used = session_mask is not None
    out: dict[str, Any] = {
        "ok": True,
        "export_api_version": EXPORT_API_VERSION,
        "lane": "research_bar",
        "engine": "monte_neo.backtest.export_single",
        "device": "cpu_numba",
        "dtype": "float64",
        "model": model.to_dict(),
        "work_checklist": model.work_checklist(session_mask_used=sess_used),
        "timing": _timing(elapsed_s=elapsed, includes_signal_build=False),
        "metrics": {
            "total_return": float(raw["total_return"]),
            "max_drawdown": float(raw["max_drawdown"]),
            "n_trades": int(raw["n_trades"]),
            "n_closed_trades": int(raw.get("n_closed_trades", raw["n_trades"])),
            "final_cash": float(raw["final_cash"]),
        },
        "bars": int(np.asarray(close).shape[0]),
    }
    if include_equity:
        eq = np.asarray(raw["equity"], dtype=np.float64)
        stride = max(1, int(equity_stride))
        out["equity"] = eq[::stride]
        out["equity_stride"] = stride
    if include_journal:
        out["journal"] = list(raw.get("trades") or [])
    if memory_plan:
        out["memory"] = plan_research_bytes(
            n_bars=int(np.asarray(close).shape[0]),
            n_combos=1,
            include_equity=include_equity,
        )
    return out


def export_batch(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signals: np.ndarray,
    model: ExecutionModel | None = None,
    *,
    device: str = "auto",
    session_mask: np.ndarray | None = None,
) -> dict[str, Any]:
    """Batch research path (Numba / Metal) with disclosed device + timer."""
    model = model or ExecutionModel()
    t0 = time.perf_counter()
    raw = run_bar_backtest_batch(
        open_,
        high,
        low,
        close,
        signals,
        model=model,
        device=device,
        session_mask=session_mask,
    )
    # Prefer engine-reported elapsed when present (excludes Python wrap noise).
    engine_elapsed = float(raw.get("elapsed_s") or (time.perf_counter() - t0))
    sess_used = session_mask is not None
    rets = np.asarray(raw["total_returns"], dtype=np.float64)
    n = int(rets.shape[0])
    out = {
        "ok": True,
        "export_api_version": EXPORT_API_VERSION,
        "lane": "research_bar",
        "engine": "monte_neo.backtest.export_batch",
        "device": raw.get("device", device),
        "dtype": "float32" if str(raw.get("device", "")).startswith("metal") else "float64",
        "model": model.to_dict(),
        "work_checklist": model.work_checklist(session_mask_used=sess_used),
        "timing": _timing(elapsed_s=engine_elapsed, includes_signal_build=False),
        "combos": n,
        "combos_per_s": float(raw.get("combos_per_s") or (n / engine_elapsed if engine_elapsed > 0 else 0.0)),
        "metrics": {
            "total_returns": rets,
            "best_return": float(raw.get("best_return", float(np.max(rets)) if n else 0.0)),
        },
        "bars": int(np.asarray(close).shape[0]),
        "memory": plan_research_bytes(
            n_bars=int(np.asarray(close).shape[0]), n_combos=n, include_signals=True
        ),
    }
    if raw.get("fallback_reason"):
        out["fallback_reason"] = raw["fallback_reason"]
    return out


def export_sma_sweep(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    *,
    combos: int = 256,
    model: ExecutionModel | None = None,
    device: str = "auto",
) -> dict[str, Any]:
    """SMA grid convenience export — timer includes signal build."""
    model = model or ExecutionModel(side_mode="long_flat")
    t0 = time.perf_counter()
    raw = run_sma_sweep(
        open_, high, low, close, combos=combos, model=model, device=device
    )
    wrap_elapsed = time.perf_counter() - t0
    # Prefer inner batch timer; still flag that signal build is inside this path.
    inner = float(raw.get("elapsed_s") or wrap_elapsed)
    out = {
        "ok": bool(raw.get("ok", True)),
        "export_api_version": EXPORT_API_VERSION,
        "lane": "research_bar",
        "engine": "monte_neo.backtest.export_sma_sweep",
        "device": raw.get("device", device),
        "signal_device": raw.get("signal_device"),
        "dtype": "float32" if str(raw.get("device", "")).startswith("metal") else "float64",
        "model": model.to_dict(),
        "work_checklist": model.work_checklist(),
        "timing": {
            **_timing(elapsed_s=inner, includes_signal_build=True),
            "signal_elapsed_s": raw.get("signal_elapsed_s"),
            "economics_elapsed_s": raw.get("economics_elapsed_s"),
        },
        "combos": int(raw.get("combos", combos)),
        "combos_per_s": float(raw.get("combos_per_s") or 0.0),
        "metrics": {
            "best_return": float(raw.get("best_return", 0.0)),
            "rows": raw.get("rows", []),
        },
        "bars": int(np.asarray(close).shape[0]),
        "note": "SMA sweep builds signals inside the reported path",
    }
    if raw.get("fallback_reason"):
        out["fallback_reason"] = raw["fallback_reason"]
    return out


def verify_export_golden(
    *,
    device: str = "cpu_numba",
    rtol: float | None = None,
    atol: float | None = None,
) -> dict[str, Any]:
    """Run golden vectors and wrap with export metadata.

    Tolerances default inside :func:`verify_golden_vectors` (strict float64, or
    Metal float32 band when the batch device resolves to Metal).
    """
    report = verify_golden_vectors(device=device, rtol=rtol, atol=atol)
    return {
        "export_api_version": EXPORT_API_VERSION,
        "package_version": __version__,
        "lane": "research_bar",
        **report,
    }


def export_sma_signal(close: np.ndarray, fast: int, slow: int) -> np.ndarray:
    """Public signal helper for harnesses that build grids outside the timer."""
    return sma_signal(close, fast, slow)


__all__ = [
    "EXPORT_API_VERSION",
    "REQUIRED_WORK_KEYS",
    "export_batch",
    "export_single",
    "export_sma_signal",
    "export_sma_sweep",
    "research_manifest",
    "verify_export_golden",
]
