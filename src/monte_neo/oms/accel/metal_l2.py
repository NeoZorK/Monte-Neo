"""Metal L2 book-walk dispatch (PyObjC), Numba fallback."""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.oms.accel.match_l2_numba import walk_book_market

_L2_KERNEL = r"""
#include <metal_stdlib>
using namespace metal;

kernel void oms_l2_walk_market_flat(
    const device float* bid_px [[buffer(0)]],
    const device float* bid_sz [[buffer(1)]],
    const device float* ask_px [[buffer(2)]],
    const device float* ask_sz [[buffer(3)]],
    const device int* sides [[buffer(4)]],
    const device float* qtys [[buffer(5)]],
    device float* out_filled [[buffer(6)]],
    device float* out_vwap [[buffer(7)]],
    device float* out_fee [[buffer(8)]],
    const device float* params [[buffer(9)]],
    uint id [[thread_position_in_grid]]
) {
    int depth = int(params[0]);
    float commission_bps = params[1];
    float slip_bps = params[2];
    float fee_rate = commission_bps * 1e-4f;
    float slip = slip_bps * 1e-4f;
    int side = sides[id];
    float need = qtys[id];
    float notional = 0.0f;
    float filled = 0.0f;
    for (int i = 0; i < depth; ++i) {
        if (need <= 1e-15f) break;
        float px = (side > 0) ? ask_px[i] : bid_px[i];
        float sz = (side > 0) ? ask_sz[i] : bid_sz[i];
        if (px <= 0.0f || sz <= 0.0f) break;
        float take = (need < sz) ? need : sz;
        float fill_px = px * (1.0f + ((float)side) * slip);
        notional += take * fill_px;
        filled += take;
        need -= take;
    }
    out_filled[id] = filled;
    out_vwap[id] = (filled > 0.0f) ? (notional / filled) : 0.0f;
    out_fee[id] = fabs(notional) * fee_rate;
}
"""


class MetalL2Engine:
    """Compile-once Metal runner for batched L2 market walks."""

    def __init__(self) -> None:
        import Metal

        self._Metal = Metal
        self.device = Metal.MTLCreateSystemDefaultDevice()
        if self.device is None:
            raise RuntimeError("No Metal device")
        self.queue = self.device.newCommandQueue()
        lib, err = self.device.newLibraryWithSource_options_error_(
            _L2_KERNEL, None, None
        )
        if lib is None:
            raise RuntimeError(f"Metal L2 shader compile failed: {err}")
        fn = lib.newFunctionWithName_("oms_l2_walk_market_flat")
        pipe, err = self.device.newComputePipelineStateWithFunction_error_(fn, None)
        if pipe is None:
            raise RuntimeError(f"Metal L2 pipeline failed: {err}")
        self.pipe = pipe
        self._shared = Metal.MTLResourceStorageModeShared

    def _buf(self, arr: np.ndarray):
        return self.device.newBufferWithBytes_length_options_(
            arr.tobytes(), arr.nbytes, self._shared
        )

    def walk_batch(
        self,
        sides: np.ndarray,
        qtys: np.ndarray,
        bid_px: np.ndarray,
        bid_sz: np.ndarray,
        ask_px: np.ndarray,
        ask_sz: np.ndarray,
        commission_bps: float,
        slip_bps: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        sides_i = np.ascontiguousarray(sides, dtype=np.int32)
        qtys_f = np.ascontiguousarray(qtys, dtype=np.float32)
        n = int(sides_i.shape[0])
        depth = int(bid_px.shape[0])
        bid_px_f = np.ascontiguousarray(bid_px, dtype=np.float32)
        bid_sz_f = np.ascontiguousarray(bid_sz, dtype=np.float32)
        ask_px_f = np.ascontiguousarray(ask_px, dtype=np.float32)
        ask_sz_f = np.ascontiguousarray(ask_sz, dtype=np.float32)
        params = np.array(
            [float(depth), float(commission_bps), float(slip_bps)], dtype=np.float32
        )
        b_bid_px = self._buf(bid_px_f)
        b_bid_sz = self._buf(bid_sz_f)
        b_ask_px = self._buf(ask_px_f)
        b_ask_sz = self._buf(ask_sz_f)
        b_sides = self._buf(sides_i)
        b_qtys = self._buf(qtys_f)
        b_filled = self.device.newBufferWithLength_options_(n * 4, self._shared)
        b_vwap = self.device.newBufferWithLength_options_(n * 4, self._shared)
        b_fee = self.device.newBufferWithLength_options_(n * 4, self._shared)
        b_params = self._buf(params)

        cmd = self.queue.commandBuffer()
        enc = cmd.computeCommandEncoder()
        enc.setComputePipelineState_(self.pipe)
        for i, buf in enumerate(
            [
                b_bid_px,
                b_bid_sz,
                b_ask_px,
                b_ask_sz,
                b_sides,
                b_qtys,
                b_filled,
                b_vwap,
                b_fee,
                b_params,
            ]
        ):
            enc.setBuffer_offset_atIndex_(buf, 0, i)
        tpt = int(self.pipe.maxTotalThreadsPerThreadgroup())
        tg = max(1, (n + tpt - 1) // tpt)
        enc.dispatchThreadgroups_threadsPerThreadgroup_((tg, 1, 1), (tpt, 1, 1))
        enc.endEncoding()
        cmd.commit()
        cmd.waitUntilCompleted()
        filled = np.frombuffer(b_filled.contents().as_buffer(n * 4), dtype=np.float32).copy()
        vwap = np.frombuffer(b_vwap.contents().as_buffer(n * 4), dtype=np.float32).copy()
        fee = np.frombuffer(b_fee.contents().as_buffer(n * 4), dtype=np.float32).copy()
        return filled.astype(np.float64), vwap.astype(np.float64), fee.astype(np.float64)


_metal_l2: MetalL2Engine | None | bool = False


def get_metal_l2_engine() -> MetalL2Engine | None:
    global _metal_l2
    if _metal_l2 is False:
        try:
            _metal_l2 = MetalL2Engine()
        except Exception:
            _metal_l2 = None
    return _metal_l2 if isinstance(_metal_l2, MetalL2Engine) else None


def run_l2_walk_dispatch(
    side: int,
    qty: float,
    bid_px: np.ndarray,
    bid_sz: np.ndarray,
    ask_px: np.ndarray,
    ask_sz: np.ndarray,
    *,
    commission_bps: float = 5.0,
    slip_bps: float = 0.0,
    device: str = "auto",
) -> dict[str, Any]:
    """Single L2 walk; Metal when requested/available, else Numba."""
    from monte_neo.oms.accel.device import resolve_device

    want = resolve_device(device)
    if want == "metal":
        eng = get_metal_l2_engine()
        if eng is not None:
            filled, vwap, fee = eng.walk_batch(
                np.array([side], dtype=np.int32),
                np.array([qty], dtype=np.float32),
                bid_px,
                bid_sz,
                ask_px,
                ask_sz,
                commission_bps,
                slip_bps,
            )
            return {
                "filled": float(filled[0]),
                "vwap": float(vwap[0]),
                "fee": float(fee[0]),
                "levels": -1,
                "device_used": "metal",
                "ok": True,
            }
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


def run_l2_walk_batch(
    sides: np.ndarray,
    qtys: np.ndarray,
    bid_px: np.ndarray,
    bid_sz: np.ndarray,
    ask_px: np.ndarray,
    ask_sz: np.ndarray,
    *,
    commission_bps: float = 5.0,
    slip_bps: float = 0.0,
    device: str = "auto",
) -> dict[str, Any]:
    """Batched L2 walks against one book snapshot."""
    from monte_neo.oms.accel.device import resolve_device

    want = resolve_device(device)
    sides_a = np.asarray(sides)
    qtys_a = np.asarray(qtys, dtype=np.float64)
    if want == "metal":
        eng = get_metal_l2_engine()
        if eng is not None:
            filled, vwap, fee = eng.walk_batch(
                sides_a,
                qtys_a,
                bid_px,
                bid_sz,
                ask_px,
                ask_sz,
                commission_bps,
                slip_bps,
            )
            return {
                "filled": filled,
                "vwap": vwap,
                "fee": fee,
                "device_used": "metal",
                "ok": True,
            }
    n = sides_a.shape[0]
    filled = np.empty(n, dtype=np.float64)
    vwap = np.empty(n, dtype=np.float64)
    fee = np.empty(n, dtype=np.float64)
    for i in range(n):
        f, v, fe, _ = walk_book_market(
            int(sides_a[i]),
            float(qtys_a[i]),
            np.asarray(bid_px, dtype=np.float64),
            np.asarray(bid_sz, dtype=np.float64),
            np.asarray(ask_px, dtype=np.float64),
            np.asarray(ask_sz, dtype=np.float64),
            float(commission_bps),
            float(slip_bps),
        )
        filled[i], vwap[i], fee[i] = f, v, fe
    return {
        "filled": filled,
        "vwap": vwap,
        "fee": fee,
        "device_used": "cpu_numba",
        "ok": True,
    }
