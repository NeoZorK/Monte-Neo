// L2 book-walk kernel (Metal) — economics match Numba walk_book_market.
// Runtime path uses the flat-buffer variant in metal_l2.py; keep this file
// as the canonical shader source for native bridge packaging.

#include <metal_stdlib>
using namespace metal;

kernel void oms_l2_walk_market(
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
