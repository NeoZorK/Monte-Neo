#include <metal_stdlib>
using namespace metal;

// Structure for OHLCV data
struct Candle {
    float open;
    float high;
    float low;
    float close;
    float volume;
};

// Structure for Backtest Results (per scenario)
struct BacktestResult {
    float total_return;
    int trade_count;
    float win_rate;
    float max_drawdown;
};

// Unified Backtest Kernel
// Each thread handles ONE scenario (one set of parameters or one MC path)
kernel void backtest_kernel(
    const device Candle* data [[buffer(0)]],
    device BacktestResult* results [[buffer(1)]],
    const device float* params [[buffer(2)]], // e.g., [fast_period, slow_period, sl_pct, tp_pct]
    uint scenario_id [[thread_position_in_grid]],
    uint total_candles [[constant(0)]]
) {
    // 1. Setup parameters for this thread
    float fast_p = params[scenario_id * 4 + 0];
    float slow_p = params[scenario_id * 4 + 1];
    float sl_pct = params[scenario_id * 4 + 2];
    float tp_pct = params[scenario_id * 4 + 3];

    // 2. Local state for indicator calculation
    float sum_fast = 0;
    float sum_slow = 0;
    int pos = 0; // 1 for Long, -1 for Short, 0 for None
    float entry_price = 0;
    float equity = 1.0;
    int trades = 0;
    int wins = 0;

    // 3. Simulation Loop
    int blocked_signal = 0;
    
    for (uint i = 0; i < total_candles; i++) {
        float close = data[i].close;
        
        if (i >= (uint)slow_p) {
            float sum_f = 0;
            for(uint j = 0; j < (uint)fast_p; j++) sum_f += data[i-j].close;
            float sma_f = sum_f / fast_p;

            float sum_s = 0;
            for(uint j = 0; j < (uint)slow_p; j++) sum_s += data[i-j].close;
            float sma_s = sum_s / slow_p;
            
            int signal = 0;
            if (sma_f > sma_s) signal = 1;
            else if (sma_f < sma_s) signal = -1;

            // Trade Logic
            if (pos == 0) {
                if (signal == 0) {
                    blocked_signal = 0;
                } else if (signal != blocked_signal) {
                    pos = signal;
                    entry_price = close;
                    trades++;
                }
            } else {
                // Exit logic (SL/TP)
                float pnl_pct = (pos == 1) ? (close / entry_price - 1.0f) : (entry_price / close - 1.0f);
                bool hit_sl = (pnl_pct <= -sl_pct / 100.0f);
                bool hit_tp = (pnl_pct >= tp_pct / 100.0f);
                bool hit_flip = (signal != 0 && signal != pos);

                if (hit_sl || hit_tp || hit_flip) {
                    equity *= (1.0f + pnl_pct);
                    if (pnl_pct > 0) wins++;
                    blocked_signal = signal;
                    pos = 0;
                }
            }
        }
    }

    // 4. Save results
    results[scenario_id].total_return = equity - 1.0;
    results[scenario_id].trade_count = trades;
    results[scenario_id].win_rate = (trades > 0) ? (float)wins / trades : 0;
}
