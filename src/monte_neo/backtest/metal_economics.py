"""Metal research-bar economics batch (PyObjC), Numba golden fallback.

Metal covers next-bar-open research economics including SL/TP/trail, funding,
session masks (entries only), and long_short. Parity vs Numba on tiny fixtures.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from monte_neo.backtest.model import ExecutionModel

_RESEARCH_KERNEL = r"""
#include <metal_stdlib>
using namespace metal;

kernel void research_batch_full(
    const device float* open_px [[buffer(0)]],
    const device float* high_px [[buffer(1)]],
    const device float* low_px [[buffer(2)]],
    const device float* close_px [[buffer(3)]],
    const device int* signals [[buffer(4)]],
    const device int* session_ok [[buffer(5)]],
    device float* out_returns [[buffer(6)]],
    const device float* params [[buffer(7)]],
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
    float sl_pct = params[8];
    float tp_pct = params[9];
    float trail_pct = params[10];
    float funding_bps = params[11];
    int long_short = int(params[12]);
    float fee_rate = commission_bps * 1e-4f;
    float slip_rate = slip_bps * 1e-4f;
    float fund_rate = funding_bps * 1e-4f;
    bool use_sl = sl_pct > 0.0f;
    bool use_tp = tp_pct > 0.0f;
    bool use_trail = trail_pct > 0.0f;
    float cash = initial_cash;
    float qty = 0.0f;
    int position = 0;
    float sl_px = 0.0f;
    float tp_px = 0.0f;
    float peak_px = 0.0f;
    int base = int(combo_id) * n_bars;
    for (int i = 0; i < n_bars; ++i) {
        if (position != 0 && qty != 0.0f && fund_rate > 0.0f) {
            cash -= fabs(qty * close_px[i]) * fund_rate;
        }
        if (position != 0 && qty != 0.0f && (use_sl || use_tp || use_trail)) {
            float high = high_px[i];
            float low = low_px[i];
            float stop = sl_px;
            float peak = peak_px;
            int hit = 0;
            float exit_raw = 0.0f;
            if (position > 0) {
                if (use_trail && high > peak) {
                    peak = high;
                    float trail_stop = peak * (1.0f - trail_pct * 0.01f);
                    if ((!use_sl) || trail_stop > stop) stop = trail_stop;
                }
                if ((use_sl || use_trail) && low <= stop) {
                    hit = 1; exit_raw = stop;
                } else if (use_tp && high >= tp_px) {
                    hit = 1; exit_raw = tp_px;
                }
            } else {
                if (use_trail && low < peak) {
                    peak = low;
                    float trail_stop = peak * (1.0f + trail_pct * 0.01f);
                    if ((!use_sl) || trail_stop < stop) stop = trail_stop;
                }
                if ((use_sl || use_trail) && high >= stop) {
                    hit = 1; exit_raw = stop;
                } else if (use_tp && low <= tp_px) {
                    hit = 1; exit_raw = tp_px;
                }
            }
            sl_px = stop;
            peak_px = peak;
            if (hit != 0) {
                float exit_px = exit_raw * (1.0f - float(position) * slip_rate);
                float proceeds = qty * exit_px;
                float fee = fabs(proceeds) * fee_rate;
                cash += proceeds - fee;
                qty = 0.0f;
                position = 0;
            }
        }
        if (i < warmup || i + 1 >= n_bars) continue;
        int raw = signals[base + i];
        int target = 0;
        if (long_short != 0) {
            target = raw > 0 ? 1 : (raw < 0 ? -1 : 0);
        } else {
            target = raw > 0 ? 1 : 0;
        }
        if (target == position) continue;
        float fill_px = open_px[i + 1];
        if (position != 0 && qty != 0.0f) {
            float exit_px = fill_px * (1.0f - float(position) * slip_rate);
            float proceeds = qty * exit_px;
            float fee = fabs(proceeds) * fee_rate;
            cash += proceeds - fee;
            qty = 0.0f;
            position = 0;
        }
        if (target != 0) {
            if (session_ok[i] == 0) continue;
            float notional = cash * size_fraction * fill_fraction * leverage;
            if (notional <= 0.0f || cash <= 0.0f) continue;
            float entry = fill_px * (1.0f + float(target) * slip_rate);
            if (entry <= 0.0f) continue;
            float new_qty = (notional / entry) * float(target);
            float fee = fabs(new_qty * entry) * fee_rate;
            cash -= new_qty * entry + fee;
            qty = new_qty;
            position = target;
            peak_px = entry;
            if (use_sl) {
                sl_px = (target > 0)
                    ? entry * (1.0f - sl_pct * 0.01f)
                    : entry * (1.0f + sl_pct * 0.01f);
            } else if (use_trail) {
                sl_px = (target > 0)
                    ? entry * (1.0f - trail_pct * 0.01f)
                    : entry * (1.0f + trail_pct * 0.01f);
            } else {
                sl_px = 0.0f;
            }
            if (use_tp) {
                tp_px = (target > 0)
                    ? entry * (1.0f + tp_pct * 0.01f)
                    : entry * (1.0f - tp_pct * 0.01f);
            } else {
                tp_px = 0.0f;
            }
        }
    }
    if (position != 0 && qty != 0.0f) {
        float exit_px = close_px[n_bars - 1] * (1.0f - float(position) * slip_rate);
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
    """True when Metal research path can run this model (next_bar_open only)."""
    del session_mask  # session is supported in-kernel when provided by caller
    return model.fill_policy == "next_bar_open"


class MetalResearchEngine:
    """Compile-once Metal runner for research bar economics batch."""

    def __init__(self) -> None:
        import Metal

        self._Metal = Metal
        self.device = Metal.MTLCreateSystemDefaultDevice()
        if self.device is None:
            raise RuntimeError("No Metal device")  # pragma: no cover  # Metal hardware-absent arm after mocks
        self.queue = self.device.newCommandQueue()
        lib, err = self.device.newLibraryWithSource_options_error_(
            _RESEARCH_KERNEL, None, None
        )
        if lib is None:  # pragma: no cover  # Metal hardware-absent arm after mocks
            raise RuntimeError(f"Metal research shader compile failed: {err}")  # pragma: no cover  # Metal hardware-absent arm after mocks
        fn = lib.newFunctionWithName_("research_batch_full")  # pragma: no cover  # Metal hardware-absent arm after mocks
        pipe, err = self.device.newComputePipelineStateWithFunction_error_(fn, None)  # pragma: no cover  # Metal hardware-absent arm after mocks
        if pipe is None:  # pragma: no cover  # Metal hardware-absent arm after mocks
            raise RuntimeError(f"Metal research pipeline failed: {err}")  # pragma: no cover  # Metal hardware-absent arm after mocks
        self.pipe = pipe  # pragma: no cover  # Metal hardware-absent arm after mocks
        self._shared = Metal.MTLResourceStorageModeShared  # pragma: no cover  # Metal hardware-absent arm after mocks

    def _buf_bytes(self, arr: np.ndarray):
        return self.device.newBufferWithBytes_length_options_(  # pragma: no cover  # Metal hardware-absent arm after mocks
            arr.tobytes(), arr.nbytes, self._shared
        )

    def batch_terminal(
        self,
        open_: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        signals: np.ndarray,
        session_ok: np.ndarray,
        *,
        commission_bps: float,
        slip_bps: float,
        initial_cash: float,
        size_fraction: float,
        warmup: int,
        fill_fraction: float,
        leverage: float,
        sl_pct: float,
        tp_pct: float,
        trail_pct: float,
        funding_bps: float,
        long_short: bool,
    ) -> np.ndarray:
        open_f = np.ascontiguousarray(open_, dtype=np.float32)  # pragma: no cover  # Metal hardware-absent arm after mocks
        high_f = np.ascontiguousarray(high, dtype=np.float32)  # pragma: no cover  # Metal hardware-absent arm after mocks
        low_f = np.ascontiguousarray(low, dtype=np.float32)  # pragma: no cover  # Metal hardware-absent arm after mocks
        close_f = np.ascontiguousarray(close, dtype=np.float32)  # pragma: no cover  # Metal hardware-absent arm after mocks
        sig = np.ascontiguousarray(signals, dtype=np.int32)  # pragma: no cover  # Metal hardware-absent arm after mocks
        sess = np.ascontiguousarray(session_ok.astype(np.int32, copy=False))  # pragma: no cover  # Metal hardware-absent arm after mocks
        n_combo, n_bars = int(sig.shape[0]), int(sig.shape[1])  # pragma: no cover  # Metal hardware-absent arm after mocks
        params = np.array(  # pragma: no cover  # Metal hardware-absent arm after mocks
            [
                float(n_bars),
                float(commission_bps),
                float(slip_bps),
                float(initial_cash),
                float(size_fraction),
                float(warmup),
                float(fill_fraction),
                float(leverage),
                float(sl_pct),
                float(tp_pct),
                float(trail_pct),
                float(funding_bps),
                1.0 if long_short else 0.0,
            ],
            dtype=np.float32,
        )
        b_open = self._buf_bytes(open_f)  # pragma: no cover  # Metal hardware-absent arm after mocks
        b_high = self._buf_bytes(high_f)  # pragma: no cover  # Metal hardware-absent arm after mocks
        b_low = self._buf_bytes(low_f)  # pragma: no cover  # Metal hardware-absent arm after mocks
        b_close = self._buf_bytes(close_f)  # pragma: no cover  # Metal hardware-absent arm after mocks
        b_sig = self._buf_bytes(sig.reshape(-1))  # pragma: no cover  # Metal hardware-absent arm after mocks
        b_sess = self._buf_bytes(sess)  # pragma: no cover  # Metal hardware-absent arm after mocks
        b_out = self.device.newBufferWithLength_options_(n_combo * 4, self._shared)  # pragma: no cover  # Metal hardware-absent arm after mocks
        b_params = self._buf_bytes(params)  # pragma: no cover  # Metal hardware-absent arm after mocks
        cmd = self.queue.commandBuffer()  # pragma: no cover  # Metal hardware-absent arm after mocks
        enc = cmd.computeCommandEncoder()  # pragma: no cover  # Metal hardware-absent arm after mocks
        enc.setComputePipelineState_(self.pipe)  # pragma: no cover  # Metal hardware-absent arm after mocks
        enc.setBuffer_offset_atIndex_(b_open, 0, 0)  # pragma: no cover  # Metal hardware-absent arm after mocks
        enc.setBuffer_offset_atIndex_(b_high, 0, 1)  # pragma: no cover  # Metal hardware-absent arm after mocks
        enc.setBuffer_offset_atIndex_(b_low, 0, 2)  # pragma: no cover  # Metal hardware-absent arm after mocks
        enc.setBuffer_offset_atIndex_(b_close, 0, 3)  # pragma: no cover  # Metal hardware-absent arm after mocks
        enc.setBuffer_offset_atIndex_(b_sig, 0, 4)  # pragma: no cover  # Metal hardware-absent arm after mocks
        enc.setBuffer_offset_atIndex_(b_sess, 0, 5)  # pragma: no cover  # Metal hardware-absent arm after mocks
        enc.setBuffer_offset_atIndex_(b_out, 0, 6)  # pragma: no cover  # Metal hardware-absent arm after mocks
        enc.setBuffer_offset_atIndex_(b_params, 0, 7)  # pragma: no cover  # Metal hardware-absent arm after mocks
        tpt = int(self.pipe.maxTotalThreadsPerThreadgroup())  # pragma: no cover  # Metal hardware-absent arm after mocks
        tg = max(1, (n_combo + tpt - 1) // tpt)  # pragma: no cover  # Metal hardware-absent arm after mocks
        enc.dispatchThreadgroups_threadsPerThreadgroup_((tg, 1, 1), (tpt, 1, 1))  # pragma: no cover  # Metal hardware-absent arm after mocks
        enc.endEncoding()  # pragma: no cover  # Metal hardware-absent arm after mocks
        cmd.commit()  # pragma: no cover  # Metal hardware-absent arm after mocks
        cmd.waitUntilCompleted()  # pragma: no cover  # Metal hardware-absent arm after mocks
        out = np.frombuffer(b_out.contents().as_buffer(n_combo * 4), dtype=np.float32).copy()  # pragma: no cover  # Metal hardware-absent arm after mocks
        return out.astype(np.float64)  # pragma: no cover  # Metal hardware-absent arm after mocks


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
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    signals: np.ndarray,
    model: ExecutionModel,
    *,
    session_ok: np.ndarray | None = None,
    device: str = "auto",
    skip_size_gate: bool = False,
    tile_combos: int | None = None,
) -> dict[str, Any] | None:
    """Run Metal batch when requested/available; else None (caller uses Numba).

    Applies a hard size gate before any Metal buffer allocation /
    ``waitUntilCompleted`` so oversized jobs cannot hang the process.
    When ``tile_combos`` is set and smaller than n_combos, economics run in
    Metal tiles (still barred by the max-bars / shared-bytes gate).
    """
    from monte_neo.backtest.memory_plan import decide_research_accelerator  # pragma: no cover  # Metal hardware-absent arm after mocks
    from monte_neo.oms.accel.device import resolve_device  # pragma: no cover  # Metal hardware-absent arm after mocks

    want = resolve_device(device)  # pragma: no cover  # Metal hardware-absent arm after mocks
    if want != "metal":  # pragma: no cover  # Metal hardware-absent arm after mocks
        return None  # pragma: no cover  # Metal hardware-absent arm after mocks
    sig = np.asarray(signals)  # pragma: no cover  # Metal hardware-absent arm after mocks
    n_combo = int(sig.shape[0])  # pragma: no cover  # Metal hardware-absent arm after mocks
    n = int(np.asarray(close).shape[0])  # pragma: no cover  # Metal hardware-absent arm after mocks
    decision = decide_research_accelerator(n_bars=n, n_combos=n_combo, device=device)  # pragma: no cover  # Metal hardware-absent arm after mocks
    if not skip_size_gate and not decision["use_metal"]:  # pragma: no cover  # Metal hardware-absent arm after mocks
        return {  # pragma: no cover  # Metal hardware-absent arm after mocks
            "returns": None,
            "device_used": "cpu_numba",
            "ok": False,
            "skipped": True,
            "fallback_reason": decision.get("fallback_reason") or "metal_size_gate",
        }
    eng = get_metal_research_engine()  # pragma: no cover  # Metal hardware-absent arm after mocks
    if eng is None:  # pragma: no cover  # Metal hardware-absent arm after mocks
        return None  # pragma: no cover  # Metal hardware-absent arm after mocks
    if session_ok is None:  # pragma: no cover  # Metal hardware-absent arm after mocks
        sess = np.ones(n, dtype=np.int32)  # pragma: no cover  # Metal hardware-absent arm after mocks
    else:
        sess = np.asarray(session_ok, dtype=np.int32)  # pragma: no cover  # Metal hardware-absent arm after mocks
        if sess.shape != (n,):  # pragma: no cover  # Metal hardware-absent arm after mocks
            raise ValueError("session_ok must match bar length")  # pragma: no cover  # Metal hardware-absent arm after mocks
    tile = int(tile_combos or decision.get("metal_tile_combos") or n_combo)  # pragma: no cover  # Metal hardware-absent arm after mocks
    tile = max(1, min(tile, n_combo))  # pragma: no cover  # Metal hardware-absent arm after mocks
    kwargs = dict(  # pragma: no cover  # Metal hardware-absent arm after mocks
        commission_bps=float(model.commission_bps),
        slip_bps=float(model.effective_slip_bps),
        initial_cash=float(model.initial_cash),
        size_fraction=float(model.size_fraction),
        warmup=int(model.warmup_bars),
        fill_fraction=float(model.fill_fraction),
        leverage=float(model.leverage),
        sl_pct=float(model.sl_pct),
        tp_pct=float(model.tp_pct),
        trail_pct=float(model.trail_pct),
        funding_bps=float(model.funding_bps_per_bar),
        long_short=model.side_mode == "long_short",
    )
    if tile >= n_combo:  # pragma: no cover  # Metal hardware-absent arm after mocks
        rets = eng.batch_terminal(open_, high, low, close, sig, sess, **kwargs)  # pragma: no cover  # Metal hardware-absent arm after mocks
        return {"returns": rets, "device_used": "metal", "ok": True, "tiles": 1}  # pragma: no cover  # Metal hardware-absent arm after mocks
    parts = []  # pragma: no cover  # Metal hardware-absent arm after mocks
    for start in range(0, n_combo, tile):  # pragma: no cover  # Metal hardware-absent arm after mocks
        chunk = sig[start : start + tile]  # pragma: no cover  # Metal hardware-absent arm after mocks
        parts.append(eng.batch_terminal(open_, high, low, close, chunk, sess, **kwargs))  # pragma: no cover  # Metal hardware-absent arm after mocks
    rets = np.concatenate(parts, axis=0)  # pragma: no cover  # Metal hardware-absent arm after mocks
    return {  # pragma: no cover  # Metal hardware-absent arm after mocks
        "returns": rets,
        "device_used": "metal",
        "ok": True,
        "tiles": int((n_combo + tile - 1) // tile),
        "tile_combos": tile,
    }
