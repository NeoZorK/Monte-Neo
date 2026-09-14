"""Frozen golden vectors for research-bar economics (no peer names).

External harnesses can call :func:`verify_golden_vectors` before any
throughput timer so device/driver changes cannot silently alter fills.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.backtest.bar_engine import run_bar_backtest
from monte_neo.backtest.batch import run_bar_backtest_batch
from monte_neo.backtest.data import frame_to_ohlc, synthetic_ohlcv
from monte_neo.backtest.model import ExecutionModel
from monte_neo.backtest.sweep import sma_signal

GOLDEN_SEED = 42
GOLDEN_BARS = 500
GOLDEN_WARMUP = 40
GOLDEN_SIZE_FRACTION = 0.5
GOLDEN_SMA = (10, 40)
GOLDEN_BATCH_SMAS: tuple[tuple[int, int], ...] = ((5, 30), (8, 40), (10, 40))

# Precomputed on Numba float64 reference (seed/bars frozen above).
GOLDEN_ZERO_FEE_RETURN = -0.00041863344903247945
GOLDEN_ZERO_FEE_MAX_DD = 0.00881348238870522
GOLDEN_ZERO_FEE_N_TRADES = 20
GOLDEN_FEE_RETURN = -0.010364421341364172
GOLDEN_FEE_MAX_DD = 0.016482239272855904
GOLDEN_FEE_N_TRADES = 20
GOLDEN_BATCH_RETURNS: tuple[float, ...] = (
    -0.014454350275131533,
    -0.013507454107820949,
    -0.010364421341364172,
)


def golden_ohlc() -> dict[str, np.ndarray]:
    """Deterministic OHLC fixture used by all golden checks."""
    return frame_to_ohlc(synthetic_ohlcv(GOLDEN_BARS, seed=GOLDEN_SEED))


def golden_signal(close: np.ndarray | None = None) -> np.ndarray:
    """SMA cross signal for the primary golden single path."""
    c = close if close is not None else golden_ohlc()["close"]
    return sma_signal(c, GOLDEN_SMA[0], GOLDEN_SMA[1])


def golden_models() -> tuple[ExecutionModel, ExecutionModel]:
    """Zero-fee and fee models sharing size/warmup (fee-hurts invariant)."""
    common = {
        "warmup_bars": GOLDEN_WARMUP,
        "size_fraction": GOLDEN_SIZE_FRACTION,
    }
    zero = ExecutionModel(commission_bps=0.0, slippage_bps=0.0, **common)
    fee = ExecutionModel(commission_bps=5.0, slippage_bps=5.0, **common)
    return zero, fee


def golden_fixture() -> dict[str, Any]:
    """Pack OHLC + signal + models for external harness reuse."""
    ohlc = golden_ohlc()
    zero, fee = golden_models()
    return {
        "seed": GOLDEN_SEED,
        "bars": GOLDEN_BARS,
        "ohlc": ohlc,
        "signal": golden_signal(ohlc["close"]),
        "model_zero_fee": zero,
        "model_fee": fee,
        "batch_smas": GOLDEN_BATCH_SMAS,
    }


def verify_golden_vectors(
    *,
    device: str = "cpu_numba",
    rtol: float = 1e-12,
    atol: float = 1e-14,
) -> dict[str, Any]:
    """Re-run frozen fixture and compare to precomputed Numba reference.

    Returns a structured report; raises nothing — callers decide fail policy.
    """
    fx = golden_fixture()
    ohlc = fx["ohlc"]
    sig = fx["signal"]
    zero = fx["model_zero_fee"]
    fee = fx["model_fee"]

    z = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=zero
    )
    f = run_bar_backtest(
        ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], sig, model=fee
    )
    signals = np.stack(
        [sma_signal(ohlc["close"], a, b) for a, b in GOLDEN_BATCH_SMAS]
    )
    batch = run_bar_backtest_batch(
        ohlc["open"],
        ohlc["high"],
        ohlc["low"],
        ohlc["close"],
        signals,
        model=fee,
        device=device,
    )

    checks: dict[str, bool] = {}
    checks["zero_return"] = np.isclose(
        z["total_return"], GOLDEN_ZERO_FEE_RETURN, rtol=rtol, atol=atol
    )
    checks["zero_max_dd"] = np.isclose(
        z["max_drawdown"], GOLDEN_ZERO_FEE_MAX_DD, rtol=rtol, atol=atol
    )
    checks["zero_n_trades"] = int(z["n_trades"]) == GOLDEN_ZERO_FEE_N_TRADES
    checks["fee_return"] = np.isclose(
        f["total_return"], GOLDEN_FEE_RETURN, rtol=rtol, atol=atol
    )
    checks["fee_max_dd"] = np.isclose(
        f["max_drawdown"], GOLDEN_FEE_MAX_DD, rtol=rtol, atol=atol
    )
    checks["fee_n_trades"] = int(f["n_trades"]) == GOLDEN_FEE_N_TRADES
    checks["fee_hurts"] = float(f["total_return"]) <= float(z["total_return"]) + 1e-12
    batch_ok = np.allclose(
        batch["total_returns"], GOLDEN_BATCH_RETURNS, rtol=rtol, atol=atol
    )
    checks["batch_returns"] = bool(batch_ok)
    # Batch path for pair (10,40) must match single fee path.
    checks["batch_matches_single"] = np.isclose(
        float(batch["total_returns"][2]),
        float(f["total_return"]),
        rtol=rtol,
        atol=atol,
    )

    return {
        "ok": all(checks.values()),
        "checks": checks,
        "device": batch.get("device", device),
        "observed": {
            "zero_return": float(z["total_return"]),
            "fee_return": float(f["total_return"]),
            "batch_returns": [float(x) for x in batch["total_returns"]],
        },
        "expected": {
            "zero_return": GOLDEN_ZERO_FEE_RETURN,
            "fee_return": GOLDEN_FEE_RETURN,
            "batch_returns": list(GOLDEN_BATCH_RETURNS),
        },
    }


__all__ = [
    "GOLDEN_SEED",
    "GOLDEN_BARS",
    "GOLDEN_BATCH_RETURNS",
    "GOLDEN_FEE_RETURN",
    "GOLDEN_ZERO_FEE_RETURN",
    "golden_fixture",
    "golden_models",
    "golden_ohlc",
    "golden_signal",
    "verify_golden_vectors",
]
