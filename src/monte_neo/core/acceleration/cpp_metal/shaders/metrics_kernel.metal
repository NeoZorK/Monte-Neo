#include <metal_stdlib>
#include "common.metal"

using namespace metal;

/**
 * calculate_metrics_kernel: Zero-Copy metric calculation from signals.
 * Grid: [n_pop, n_scenarios]
 */
kernel void calculate_metrics_kernel(
    const device float* prices [[buffer(0)]],      // [n_scenarios x n_time]
    const device int* signals [[buffer(1)]],       // [n_pop x n_scenarios x n_time]
    device BacktestResult* results [[buffer(2)]],  // [n_pop x n_scenarios]
    const device uint& n_time [[buffer(3)]],
    const device float* params [[buffer(4)]],      // [sl_pct, tp_pct, comm_bps, slip_bps]
    uint2 id [[thread_position_in_grid]],
    uint2 grid_size [[threads_per_grid]]
) {
    uint pop_idx = id.x;
    uint scen_idx = id.y;
    uint n_pop = grid_size.x;
    uint n_scenarios = grid_size.y;
    
    if (pop_idx >= n_pop || scen_idx >= n_scenarios) return;

    float sl_pct = params[0];
    float tp_pct = params[1];
    float commission_pct = params[2] / 10000.0f;
    float slippage_pct = params[3] / 10000.0f;
    bool use_sl_tp = (sl_pct > 0.0f || tp_pct > 0.0f);

    float equity = 1.0f;
    int pos = 0;
    float entry_price = 0.0f;
    float sl_price = 0.0f;
    float tp_price = 0.0f;
    int blocked_signal = 0;
    int trades = 0;
    int wins = 0;
    float max_dd = 0.0f;
    float peak_equity = 1.0f;
    float total_wins_val = 0.0f;
    float total_losses_val = 0.0f;
    float sum_returns = 0.0f;
    float sum_sq_returns = 0.0f;
    int return_count = 0;

    // Prices are [n_scenarios x n_time]
    uint price_base = scen_idx * n_time;
    // Signals are [n_pop x n_scenarios x n_time]
    uint signal_base = (pop_idx * n_scenarios + scen_idx) * n_time;

    for (uint i = 1; i < n_time; i++) {
        float price = prices[price_base + i];
        int sig = signals[signal_base + i];
        
        // 1. Check Exit
        if (pos != 0) {
            bool hit_exit = false;
            float exit_price = price;

            if (use_sl_tp) {
                if (pos == 1) {
                    if (price <= sl_price) { exit_price = sl_price; hit_exit = true; }
                    else if (price >= tp_price) { exit_price = tp_price; hit_exit = true; }
                } else {
                    if (price >= sl_price) { exit_price = sl_price; hit_exit = true; }
                    else if (price <= tp_price) { exit_price = tp_price; hit_exit = true; }
                }
            }

            if (!hit_exit && sig == -pos) {
                exit_price = price;
                hit_exit = true;
            }

            if (hit_exit) {
                float trade_return = (pos == 1) ? (exit_price / entry_price - 1.0f) : (1.0f - exit_price / entry_price);
                trade_return -= (commission_pct + slippage_pct) * 2.0f;
                
                equity *= (1.0f + trade_return);
                trades++;
                if (trade_return > 0) {
                    wins++;
                    total_wins_val += trade_return;
                } else {
                    total_losses_val += -trade_return;
                }
                
                sum_returns += trade_return;
                sum_sq_returns += trade_return * trade_return;
                return_count++;
                
                blocked_signal = sig;
                pos = 0;
            }
        }
        
        // 2. Check Entry
        if (pos == 0) {
            if (sig == 0) {
                blocked_signal = 0;
            } else if (sig != blocked_signal) {
                pos = (sig > 0) ? 1 : -1;
                entry_price = price;
                if (use_sl_tp) {
                    if (pos == 1) {
                        sl_price = entry_price * (1.0f - sl_pct / 100.0f);
                        tp_price = entry_price * (1.0f + tp_pct / 100.0f);
                    } else {
                        sl_price = entry_price * (1.0f + sl_pct / 100.0f);
                        tp_price = entry_price * (1.0f - tp_pct / 100.0f);
                    }
                }
            }
        }
        
        // 3. Update Metrics
        if (equity > peak_equity) peak_equity = equity;
        float dd = (peak_equity - equity) / peak_equity;
        if (dd > max_dd) max_dd = dd;
    }

    // Final result index: [pop_idx * n_scenarios + scen_idx]
    uint res_idx = pop_idx * n_scenarios + scen_idx;
    results[res_idx].total_return = equity - 1.0f;
    results[res_idx].trade_count = trades;
    results[res_idx].win_rate = (trades > 0) ? (float)wins / trades : 0.0f;
    results[res_idx].max_drawdown = max_dd;
    results[res_idx].profit_factor = (total_losses_val > 0) ? total_wins_val / total_losses_val : (total_wins_val > 0 ? 100.0f : 0.0f);
    
    if (return_count > 1) {
        float avg_ret = sum_returns / return_count;
        float variance = (sum_sq_returns / return_count) - (avg_ret * avg_ret);
        float std_dev = sqrt(max(variance, 0.000001f));
        results[res_idx].sharpe_ratio = (std_dev > 0) ? (avg_ret / std_dev) * sqrt(252.0f) : 0.0f;
    } else {
        results[res_idx].sharpe_ratio = 0.0f;
    }
}
