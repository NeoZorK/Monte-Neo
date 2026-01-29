#include <metal_stdlib>
#include "common.metal"
#include "indicators.metal"

using namespace metal;

// --- Unified Backtest Kernel ---

kernel void backtest_kernel(
    const device Candle* data [[buffer(0)]],
    device BacktestResult* results [[buffer(1)]],
    const device float* params [[buffer(2)]],
    uint scenario_id [[thread_position_in_grid]],
    device uint& total_candles [[buffer(3)]]
) {
    // 1. Setup parameters
    int strategy_type = (int)params[scenario_id * 10 + 0];
    float p1 = params[scenario_id * 10 + 1]; // Param A
    float p2 = params[scenario_id * 10 + 2]; // Param B
    float p3 = params[scenario_id * 10 + 3]; // Param C
    int atr_period = (int)params[scenario_id * 10 + 4];
    float sl_mult = params[scenario_id * 10 + 5];
    float tp_mult = params[scenario_id * 10 + 6];
    float ts_mult = params[scenario_id * 10 + 7];
    float commission_bps = params[scenario_id * 10 + 8];
    float slippage_bps = params[scenario_id * 10 + 9];

    float commission_pct = commission_bps / 10000.0f;
    float slippage_pct = slippage_bps / 10000.0f;

    // 2. State Management
    float equity = 1.0f;
    int pos = 0;
    float entry_price = 0.0f;
    float sl_price = 0.0f;
    float tp_price = 0.0f;
    int trades = 0;
    int wins = 0;
    
    // Indicator state
    float avg_gain = 0.0f;
    float avg_loss = 0.0f;
    float fast_ema = 0.0f;
    float slow_ema = 0.0f;
    float signal_ema = 0.0f;
    float current_atr = 0.0f;
    float max_dd = 0.0f;
    float peak_equity = 1.0f;
    float total_wins_val = 0.0f;
    float total_losses_val = 0.0f;
    float sum_returns = 0.0f;
    float sum_sq_returns = 0.0f;
    int return_count = 0;

    // 3. Main Loop
    for (uint i = 1; i < total_candles; i++) {
        const device Candle& c = data[i];
        const device Candle& prev_c = data[i-1];
        
        float signal_val = 0.0f;
        
        if (strategy_type == 0) { // SMA Crossover
            float sma_fast = Indicators::calculate_sma(data, i, (int)p1);
            float sma_slow = Indicators::calculate_sma(data, i, (int)p2);
            if (sma_fast > sma_slow) signal_val = 1.0f;
            else if (sma_fast < sma_slow) signal_val = -1.0f;
        } 
        else if (strategy_type == 1) { // RSI
            float rsi = Indicators::update_rsi(c.close, prev_c.close, avg_gain, avg_loss, (int)p1, i);
            if (rsi < p3) signal_val = 1.0f;      
            else if (rsi > p2) signal_val = -1.0f; 
            else signal_val = (float)pos; 
        }
        else if (strategy_type == 2) { // MACD
            fast_ema = (i == 1) ? c.close : Indicators::update_ema(c.close, fast_ema, (int)p1);
            slow_ema = (i == 1) ? c.close : Indicators::update_ema(c.close, slow_ema, (int)p2);
            float macd = fast_ema - slow_ema;
            signal_ema = (i == 1) ? macd : Indicators::update_ema(macd, signal_ema, (int)p3);
            float hist = macd - signal_ema;
            if (hist > 0) signal_val = 1.0f;
            else if (hist < 0) signal_val = -1.0f;
        }
        else if (strategy_type == 3) { // Dynamic Generic
            if (p1 == 0.0f) signal_val = Indicators::get_dynamic_signal(data, i, 0, p2, p3);
            else if (p1 == 1.0f) signal_val = Indicators::get_dynamic_signal(data, i, 1, p2, p3);
            else if (p1 == 2.0f) signal_val = Indicators::get_dynamic_signal(data, i, 2, p2, p3);
            else if (p1 == 3.0f) signal_val = Indicators::get_dynamic_signal(data, i, 3, p2, p3);
            else if (p1 == 4.0f) signal_val = Indicators::get_dynamic_signal(data, i, 4, p2, p3);
            else if (p1 == 5.0f) signal_val = Indicators::get_dynamic_signal(data, i, 5, p2, p3);
            else if (p1 == 6.0f) signal_val = Indicators::get_dynamic_signal(data, i, 6, p2, p3);
        }
        else if (strategy_type == 4) { // Logic AND/OR
             float s1_real = Indicators::get_dynamic_signal(data, i, (int)p2, p3, params[scenario_id * 10 + 4]);
             float s2_real = Indicators::get_dynamic_signal(data, i, (int)params[scenario_id * 10 + 5], params[scenario_id * 10 + 6], params[scenario_id * 10 + 7]);
             
             if (p1 == 0.0f) signal_val = (s1_real > 0 && s2_real > 0) ? 1.0f : ((s1_real < 0 && s2_real < 0) ? -1.0f : 0.0f);
             else signal_val = (s1_real > 0 || s2_real > 0) ? 1.0f : ((s1_real < 0 || s2_real < 0) ? -1.0f : 0.0f);
             
             atr_period = 14; sl_mult = 1.5f; tp_mult = 3.0f; ts_mult = 2.0f;
         }
        else if (strategy_type == 5) { // Bollinger Bands
            float sma = Indicators::calculate_sma(data, i, (int)p1);
            float stddev = Indicators::calculate_stddev(data, i, (int)p1, sma);
            float upper = sma + (stddev * p2);
            float lower = sma - (stddev * p2);
            if (c.close < lower) signal_val = 1.0f;      
            else if (c.close > upper) signal_val = -1.0f; 
            else signal_val = (float)pos;
        }

        current_atr = Indicators::update_atr(c, prev_c, current_atr, atr_period, i);

        if (pos == 0) {
            if (signal_val == 1.0f || signal_val == -1.0f) {
                pos = (signal_val == 1.0f) ? 1 : -1;
                entry_price = c.close * (1.0f + (float)pos * slippage_pct);
                equity *= (1.0f - commission_pct); 
                sl_price = entry_price - (float)pos * (current_atr * sl_mult);
                tp_price = entry_price + (float)pos * (current_atr * tp_mult);
                trades++;
            }
        } else {
            if (ts_mult > 0) {
                if (pos == 1) {
                    float new_sl = c.close - (current_atr * ts_mult);
                    if (new_sl > sl_price) sl_price = new_sl;
                } else {
                    float new_sl = c.close + (current_atr * ts_mult);
                    if (new_sl < sl_price) sl_price = new_sl;
                }
            }

            bool exit = false; float pnl_pct = 0.0f;
            if (pos == 1) {
                if (c.low <= sl_price) { exit = true; pnl_pct = (sl_price * (1.0f - slippage_pct) / entry_price) - 1.0f; }
                else if (c.high >= tp_price) { exit = true; pnl_pct = (tp_price * (1.0f - slippage_pct) / entry_price) - 1.0f; }
                else if (signal_val <= 0.0f) { exit = true; pnl_pct = (c.close * (1.0f - slippage_pct) / entry_price) - 1.0f; }
            } else {
                if (c.high >= sl_price) { exit = true; pnl_pct = (entry_price / (sl_price * (1.0f + slippage_pct))) - 1.0f; }
                else if (c.low <= tp_price) { exit = true; pnl_pct = (entry_price / (tp_price * (1.0f + slippage_pct))) - 1.0f; }
                else if (signal_val >= 0.0f) { exit = true; pnl_pct = (entry_price / (c.close * (1.0f + slippage_pct))) - 1.0f; }
            }

            if (exit) {
                equity *= (1.0f + pnl_pct);
                equity *= (1.0f - commission_pct); 
                sum_returns += pnl_pct;
                sum_sq_returns += pnl_pct * pnl_pct;
                return_count++;
                if (pnl_pct > 0) { wins++; total_wins_val += pnl_pct; }
                else { total_losses_val += abs(pnl_pct); }
                pos = 0;
                if (equity > peak_equity) peak_equity = equity;
                float dd = (peak_equity - equity) / peak_equity;
                if (dd > max_dd) max_dd = dd;
            }
        }
    }

    float sharpe = 0.0f;
    if (return_count > 1) {
        float mean = sum_returns / (float)return_count;
        float variance = (sum_sq_returns / (float)return_count) - (mean * mean);
        if (variance > 1e-9f) sharpe = (mean / sqrt(variance)) * sqrt(252.0f);
    }

    results[scenario_id].total_return = equity - 1.0f;
    results[scenario_id].trade_count = trades;
    results[scenario_id].win_rate = (trades > 0) ? (float)wins / trades : 0.0f;
    results[scenario_id].max_drawdown = max_dd;
    results[scenario_id].profit_factor = (total_losses_val > 0) ? (total_wins_val / total_losses_val) : (total_wins_val > 0 ? 100.0f : 1.0f);
    results[scenario_id].sharpe_ratio = sharpe;
}
