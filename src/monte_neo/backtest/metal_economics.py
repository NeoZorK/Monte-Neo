"""Metal research-bar economics batch (PyObjC), Numba golden fallback.

Metal covers the long/flat next-bar-open subset (fees + slip + fill_fraction +
leverage). SL/TP/trail/funding/session/long_short stay on Numba golden.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.backtest.model import ExecutionModel

_RESEARCH_KERNEL = r"""
#include <metal_stdlib>
using namespace metal;

kernel void research_batch_long_flat(
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
    float fill_fraction = params[6];
    float leverage = params[7];
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
            float notional = cash * size_fraction * fill_fraction * leverage;
            float entry = fill_px * (1.0f + slip_rate);
            if (entry <= 0.0f || notional <= 0.0f || cash <= 0.0f) continue;
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


def metal_economics_eligible(
    model: ExecutionModel,
    session_mask: np.ndarray | None = None,
) -> bool:
    """True when Metal long/flat subset matches Numba golden for this model."""
    if model.side_mode != "long_flat":
        return False
    if model.fill_policy != "next_bar_open":
        return False
    if model.sl_pct > 0.0 or model.tp_pct > 0.0 or model.trail_pct > 0.0:
        return False
    if model.funding_bps_per_bar > 0.0:
        return False
    if session_mask is not None and not bool(np.all(session_mask)):
        return False
    return True


class MetalResearchEngine:
    """Compile-once Metal runner for research bar long/flat batch."""

    def __init__(self) -> None:
        import Metal

        self._Metal = Metal
        self.device = Metal.MTLCreateSystemDefaultDevice()
        if self.device is None:
            raise RuntimeError("No Metal device")
        self.queue = self.device.newCommandQueue()
        lib, err = self.device.newLibraryWithSource_options_error_(
            _RESEARCH_KERNEL, None, None
        )
        if lib is None:
            raise RuntimeError(f"Metal research shader compile failed: {err}")
        fn = lib.newFunctionWithName_("research_batch_long_flat")
        pipe, err = self.device.newComputePipelineStateWithFunction_error_(fn, None)
        if pipe is None:
            raise RuntimeError(f"Metal research pipeline failed: {err}")
        self.pipe = pipe
        self._shared = Metal.MTLResourceStorageModeShared

    def _buf_bytes(self, arr: np.ndarray):
        return self.device.newBufferWithBytes_length_options_(
            arr.tobytes(), arr.nbytes, self._shared
        )

    def batch_terminal(
        self,
        open_: np.ndarray,
        close: np.ndarray,
        signals: np.ndarray,
        *,
        commission_bps: float,
        slip_bps: float,
        initial_cash: float,
        size_fraction: float,
        warmup: int,
        fill_fraction: float,
        leverage: float,
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
                float(fill_fraction),
                float(leverage),
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


_metal_research: MetalResearchEngine | None | bool = False


def get_metal_research_engine() -> MetalResearchEngine | None:
    global _metal_research
    if _metal_research is False:
        try:
            _metal_research = MetalResearchEngine()
        except Exception:
            _metal_research = None
    return _metal_research if isinstance(_metal_research, MetalResearchEngine) else None


def try_metal_batch_returns(
    open_: np.ndarray,
    close: np.ndarray,
    signals: np.ndarray,
    model: ExecutionModel,
    *,
    device: str = "auto",
) -> dict[str, Any] | None:
    """Run Metal batch when requested/available; else None (caller uses Numba)."""
    from monte_neo.oms.accel.device import resolve_device

    want = resolve_device(device)
    if want != "metal":
        return None
    eng = get_metal_research_engine()
    if eng is None:
        return None
    rets = eng.batch_terminal(
        open_,
        close,
        signals,
        commission_bps=float(model.commission_bps),
        slip_bps=float(model.effective_slip_bps),
        initial_cash=float(model.initial_cash),
        size_fraction=float(model.size_fraction),
        warmup=int(model.warmup_bars),
        fill_fraction=float(model.fill_fraction),
        leverage=float(model.leverage),
    )
    return {"returns": rets, "device_used": "metal", "ok": True}
