// OMS bar-match kernel scaffold (Metal).
// Full wiring via native bridge in a follow-up build; economics must match
// Numba/CPU reference (parity tests). Designed for M1 Pro unified memory.

#include <metal_stdlib>
using namespace metal;

struct OmsBar {
    float open_px;
    float high_px;
    float low_px;
    float close_px;
};

struct OmsMatchParams {
    float commission_bps;
    float slippage_bps;
    float size_fraction;
    float initial_cash;
    int warmup;
    int n_bars;
};

kernel void oms_batch_long_flat(
    const device OmsBar* bars [[buffer(0)]],
    const device int* signals [[buffer(1)]], // (n_combo * n_bars)
    device float* out_returns [[buffer(2)]],
    constant OmsMatchParams& p [[buffer(3)]],
    uint combo_id [[thread_position_in_grid]]
) {
    float fee_rate = p.commission_bps * 1e-4f;
    float slip_rate = p.slippage_bps * 1e-4f;
    float cash = p.initial_cash;
    float qty = 0.0f;
    int position = 0;
    int n = p.n_bars;
    int base = int(combo_id) * n;

    for (int i = 0; i < n; ++i) {
        if (i < p.warmup || i + 1 >= n) {
            continue;
        }
        int target = signals[base + i] > 0 ? 1 : 0;
        if (target == position) {
            continue;
        }
        float fill_px = bars[i + 1].open_px;
        if (position != 0 && qty != 0.0f) {
            float exit_px = fill_px * (1.0f - slip_rate);
            float proceeds = qty * exit_px;
            float fee = fabs(proceeds) * fee_rate;
            cash += proceeds - fee;
            qty = 0.0f;
            position = 0;
        }
        if (target != 0) {
            float notional = cash * p.size_fraction;
            float entry = fill_px * (1.0f + slip_rate);
            if (entry <= 0.0f || notional <= 0.0f) {
                continue;
            }
            qty = notional / entry;
            float fee = fabs(qty * entry) * fee_rate;
            cash -= qty * entry + fee;
            position = 1;
        }
    }
    if (position != 0 && qty != 0.0f) {
        float exit_px = bars[n - 1].close_px * (1.0f - slip_rate);
        float proceeds = qty * exit_px;
        float fee = fabs(proceeds) * fee_rate;
        cash += proceeds - fee;
    }
    out_returns[combo_id] = cash / p.initial_cash - 1.0f;
}
