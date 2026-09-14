"""Metal compute dispatch for OMS batch kernels (PyObjC), Numba fallback."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.oms.accel.match_l2_numba import walk_book_market
from monte_neo.oms.accel.match_numba import batch_terminal_long_flat

_BATCH_KERNEL = r"""
#include <metal_stdlib>
using namespace metal;

kernel void oms_batch_long_flat_flat(
    const device float* open_px [[buffer(0)]],
    const device float* close_px [[buffer(1)]],
    const device int* signals [[buffer(2)]],
    device float* out_returns [[buffer(3)]],
    const device float* params [[buffer(4)]],
    uint combo_id [[thread_position_in_grid]]
) {
    int n_bars = int(params[0]);
    float commission_bps = params[1];
    float slip_bps = params[2];
    float initial_cash = params[3];
    float size_fraction = params[4];
    int warmup = int(params[5]);
    float fee_rate = commission_bps * 1e-4f;
    float slip_rate = slip_bps * 1e-4f;
    float cash = initial_cash;
    float qty = 0.0f;
    int position = 0;
    int base = int(combo_id) * n_bars;
    for (int i = 0; i < n_bars; ++i) {
        if (i < warmup || i + 1 >= n_bars) continue;
        int target = signals[base + i] > 0 ? 1 : 0;
        if (target == position) continue;
        float fill_px = open_px[i + 1];
        if (position != 0 && qty != 0.0f) {
            float exit_px = fill_px * (1.0f - slip_rate);
            float proceeds = qty * exit_px;
            float fee = fabs(proceeds) * fee_rate;
            cash += proceeds - fee;
            qty = 0.0f;
            position = 0;
        }
        if (target != 0) {
            float notional = cash * size_fraction;
            float entry = fill_px * (1.0f + slip_rate);
            if (entry <= 0.0f || notional <= 0.0f) continue;
            qty = notional / entry;
            float fee = fabs(qty * entry) * fee_rate;
            cash -= qty * entry + fee;
            position = 1;
        }
    }
    if (position != 0 && qty != 0.0f) {
        float exit_px = close_px[n_bars - 1] * (1.0f - slip_rate);
        float proceeds = qty * exit_px;
        float fee = fabs(proceeds) * fee_rate;
        cash += proceeds - fee;
    }
    out_returns[combo_id] = cash / initial_cash - 1.0f;
}
"""


class MetalOmsEngine:
    """Compile-once Metal runner for OMS batch long/flat."""

    def __init__(self) -> None:
        import Metal

        self._Metal = Metal
        self.device = Metal.MTLCreateSystemDefaultDevice()
        if self.device is None:
            raise RuntimeError("No Metal device")
        self.queue = self.device.newCommandQueue()
        lib, err = self.device.newLibraryWithSource_options_error_(
            _BATCH_KERNEL, None, None
        )
        if lib is None:
            raise RuntimeError(f"Metal shader compile failed: {err}")
        fn = lib.newFunctionWithName_("oms_batch_long_flat_flat")
        pipe, err = self.device.newComputePipelineStateWithFunction_error_(fn, None)
        if pipe is None:
            raise RuntimeError(f"Metal pipeline failed: {err}")
        self.pipe = pipe
        self._shared = Metal.MTLResourceStorageModeShared

    def _buf_bytes(self, arr: np.ndarray):
        return self.device.newBufferWithBytes_length_options_(
            arr.tobytes(), arr.nbytes, self._shared
        )

    def batch_terminal_long_flat(
        self,
        open_: np.ndarray,
        close: np.ndarray,
        signals: np.ndarray,
        commission_bps: float,
        slip_bps: float,
        initial_cash: float,
        size_fraction: float,
        warmup: int,
    ) -> np.ndarray:
        open_f = np.ascontiguousarray(open_, dtype=np.float32)
        close_f = np.ascontiguousarray(close, dtype=np.float32)
        sig = np.ascontiguousarray(signals, dtype=np.int32)
        n_combo, n_bars = int(sig.shape[0]), int(sig.shape[1])
        params = np.array(
            [
                float(n_bars),
                float(commission_bps),
                float(slip_bps),
                float(initial_cash),
                float(size_fraction),
                float(warmup),
            ],
            dtype=np.float32,
        )
        b_open = self._buf_bytes(open_f)
        b_close = self._buf_bytes(close_f)
        b_sig = self._buf_bytes(sig.reshape(-1))
        b_out = self.device.newBufferWithLength_options_(n_combo * 4, self._shared)
        b_params = self._buf_bytes(params)

        cmd = self.queue.commandBuffer()
        enc = cmd.computeCommandEncoder()
        enc.setComputePipelineState_(self.pipe)
        enc.setBuffer_offset_atIndex_(b_open, 0, 0)
        enc.setBuffer_offset_atIndex_(b_close, 0, 1)
        enc.setBuffer_offset_atIndex_(b_sig, 0, 2)
        enc.setBuffer_offset_atIndex_(b_out, 0, 3)
        enc.setBuffer_offset_atIndex_(b_params, 0, 4)
        tpt = int(self.pipe.maxTotalThreadsPerThreadgroup())
        tg = max(1, (n_combo + tpt - 1) // tpt)
        enc.dispatchThreadgroups_threadsPerThreadgroup_((tg, 1, 1), (tpt, 1, 1))
        enc.endEncoding()
        cmd.commit()
        cmd.waitUntilCompleted()
        out = np.frombuffer(b_out.contents().as_buffer(n_combo * 4), dtype=np.float32).copy()
        return out.astype(np.float64)


_metal_engine: MetalOmsEngine | None | bool = False


def get_metal_oms_engine() -> MetalOmsEngine | None:
    global _metal_engine
    if _metal_engine is False:
        try:
            _metal_engine = MetalOmsEngine()
        except Exception:
            _metal_engine = None
    return _metal_engine if isinstance(_metal_engine, MetalOmsEngine) else None


def run_batch_terminal(
    open_: np.ndarray,
    close: np.ndarray,
    signals: np.ndarray,
    *,
    commission_bps: float = 5.0,
    slip_bps: float = 5.0,
    initial_cash: float = 100_000.0,
    size_fraction: float = 1.0,
    warmup: int = 0,
    device: str = "auto",
) -> dict[str, Any]:
    """Dispatch OMS batch long/flat; prefer Metal when available."""
    from monte_neo.oms.accel.device import resolve_device

    want = resolve_device(device)
    if want == "metal":
        eng = get_metal_oms_engine()
        if eng is not None:
            rets = eng.batch_terminal_long_flat(
                open_,
                close,
                signals,
                commission_bps,
                slip_bps,
                initial_cash,
                size_fraction,
                warmup,
            )
            return {"returns": rets, "device_used": "metal", "ok": True}
    rets = batch_terminal_long_flat(
        np.asarray(open_, dtype=np.float64),
        np.asarray(close, dtype=np.float64),
        np.asarray(signals, dtype=np.int64),
        float(commission_bps),
        float(slip_bps),
        float(initial_cash),
        float(size_fraction),
        int(warmup),
    )
    return {"returns": rets, "device_used": "cpu_numba", "ok": True}


def run_l2_walk(
    side: int,
    qty: float,
    bid_px: np.ndarray,
    bid_sz: np.ndarray,
    ask_px: np.ndarray,
    ask_sz: np.ndarray,
    *,
    commission_bps: float = 5.0,
    slip_bps: float = 0.0,
    device: str = "cpu_numba",
) -> dict[str, Any]:
    """L2 walk via Numba golden path (Metal L2 scaffold reserved for native wire)."""
    _ = device
    filled, vwap, fee, levels = walk_book_market(
        int(side),
        float(qty),
        np.asarray(bid_px, dtype=np.float64),
        np.asarray(bid_sz, dtype=np.float64),
        np.asarray(ask_px, dtype=np.float64),
        np.asarray(ask_sz, dtype=np.float64),
        float(commission_bps),
        float(slip_bps),
    )
    return {
        "filled": float(filled),
        "vwap": float(vwap),
        "fee": float(fee),
        "levels": int(levels),
        "device_used": "cpu_numba",
        "ok": True,
    }
