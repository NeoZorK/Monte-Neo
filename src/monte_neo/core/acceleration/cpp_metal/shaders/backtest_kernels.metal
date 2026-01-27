#include <metal_stdlib>
using namespace metal;

// --- Data Structures ---

struct Candle {
    float open;
    float high;
    float low;
    float close;
    float volume;
};

struct BacktestResult {
    float total_return;
    int trade_count;
    float win_rate;
    float max_drawdown;
    float profit_factor;
    float sharpe_ratio;
};

// --- Indicator Library (Inline for maximum performance) ---

struct Indicators {
    // Simple Moving Average
    static float calculate_sma(const device Candle* data, int index, int period) {
        if (index < period - 1) return 0.0f;
        float sum = 0.0f;
        for (int i = 0; i < period; i++) {
            sum += data[index - i].close;
        }
        return sum / (float)period;
    }

    // Exponential Moving Average
    // Note: In a real-time kernel, we should pass the previous EMA value to avoid O(N) recalculation
    // But for a stateless parallel call, we might need a sliding window or pre-calculated buffers.
    // For our Unified Kernel, we maintain state across the loop.
    static float update_ema(float current_val, float prev_ema, int period) {
        float alpha = 2.0f / (float)(period + 1);
        return (current_val - prev_ema) * alpha + prev_ema;
    }

    // Relative Strength Index (RSI)
    // Returns a value between 0 and 100
    static float update_rsi(float current_close, float prev_close, thread float &avg_gain, thread float &avg_loss, int period, int step) {
        float change = current_close - prev_close;
        float gain = max(0.0f, change);
        float loss = max(0.0f, -change);

        if (step < period) {
            avg_gain += gain;
            avg_loss += loss;
            if (step == period - 1) {
                avg_gain /= (float)period;
                avg_loss /= (float)period;
            }
            return 50.0f;
        } else {
            avg_gain = (avg_gain * (float)(period - 1) + gain) / (float)period;
            avg_loss = (avg_loss * (float)(period - 1) + loss) / (float)period;
            
            if (avg_loss == 0.0f) return 100.0f;
            float rs = avg_gain / avg_loss;
            return 100.0f - (100.0f / (1.0f + rs));
        }
    }

    // Average True Range (ATR)
    static float update_atr(const device Candle& current, const device Candle& prev, float prev_atr, int period, int step) {
        float tr = max(current.high - current.low, 
                   max(abs(current.high - prev.close), 
                       abs(current.low - prev.close)));
        
        if (step < period) {
            return tr; // Initial TR
        } else {
            return (prev_atr * (float)(period - 1) + tr) / (float)period;
        }
    }

    static float get_dynamic_signal(const device Candle* data, int i, int sub_type, float p2, float p3) {
        if (sub_type == 0) { // Price > SMA
            float sma = calculate_sma(data, i, (int)p2);
            return (data[i].close > sma) ? 1.0f : -1.0f;
        } else if (sub_type == 1) { // Price > Max
            float rolling_max = calculate_max(data, i-1, (int)p2);
            return (data[i].close > rolling_max) ? 1.0f : 0.0f;
        } else if (sub_type == 2) { // Price < Min
            float rolling_min = calculate_min(data, i-1, (int)p2);
            return (data[i].close < rolling_min) ? -1.0f : 0.0f;
        } else if (sub_type == 3) { // Diff > 0
            float diff = data[i].close - data[i-(int)p2].close;
            return (diff > 0.0f) ? 1.0f : -1.0f;
        } else if (sub_type == 4) { // Price < SMA
            float sma = calculate_sma(data, i, (int)p2);
            return (data[i].close < sma) ? 1.0f : -1.0f;
        } else if (sub_type == 5) { // SMA_f < SMA_s
            float sma_fast = calculate_sma(data, i, (int)p2);
            float sma_slow = calculate_sma(data, i, (int)p3);
            return (sma_fast < sma_slow) ? 1.0f : -1.0f;
        } else if (sub_type == 6) { // Diff < 0
            float diff = data[i].close - data[i-(int)p2].close;
            return (diff < 0.0f) ? 1.0f : -1.0f;
        } else if (sub_type == 10) { // Price < BB Lower
            float sma = calculate_sma(data, i, (int)p2);
            float stddev = calculate_stddev(data, i, (int)p2, sma);
            return (data[i].close < (sma - stddev * p3)) ? 1.0f : 0.0f;
        } else if (sub_type == 11) { // Price > BB Upper
            float sma = calculate_sma(data, i, (int)p2);
            float stddev = calculate_stddev(data, i, (int)p2, sma);
            return (data[i].close > (sma + stddev * p3)) ? -1.0f : 0.0f;
        } else if (sub_type == 12) { // RSI < Threshold
            float rsi = calculate_rsi_window(data, i, (int)p2);
            return (rsi < p3) ? 1.0f : 0.0f;
        } else if (sub_type == 13) { // RSI > Threshold
            float rsi = calculate_rsi_window(data, i, (int)p2);
            return (rsi > p3) ? -1.0f : 0.0f;
        }
        return 0.0f;
    }

    // Rolling Max
    static float calculate_max(const device Candle* data, int index, int period) {
        if (index < period - 1) return 0.0f;
        float val = data[index].high;
        for (int i = 1; i < period; i++) {
            if (data[index - i].high > val) val = data[index - i].high;
        }
        return val;
    }

    // Rolling Min
    static float calculate_min(const device Candle* data, int index, int period) {
        if (index < period - 1) return 0.0f;
        float val = data[index].low;
        for (int i = 1; i < period; i++) {
            if (data[index - i].low < val) val = data[index - i].low;
        }
        return val;
    }

    // Standard Deviation
    static float calculate_stddev(const device Candle* data, int index, int period, float mean) {
        if (index < period - 1) return 0.0f;
        float sum_sq_diff = 0.0f;
        for (int i = 0; i < period; i++) {
            float diff = data[index - i].close - mean;
            sum_sq_diff += diff * diff;
        }
        return sqrt(sum_sq_diff / (float)period);
    }

    // Window-based RSI (Simple)
    static float calculate_rsi_window(const device Candle* data, int index, int period) {
        if (index <= period) return 50.0f;
        float gains = 0.0f;
        float losses = 0.0f;
        for (int i = 0; i < period; i++) {
            float diff = data[index - i].close - data[index - i - 1].close;
            if (diff > 0) gains += diff;
            else losses -= diff;
        }
        if (losses == 0) return 100.0f;
        float rs = (gains / (float)period) / (losses / (float)period);
        return 100.0f - (100.0f / (1.0f + rs));
    }
};

// --- Unified Backtest Kernel ---

kernel void backtest_kernel(
    const device Candle* data [[buffer(0)]],
    device BacktestResult* results [[buffer(1)]],
    const device float* params [[buffer(2)]],
    uint scenario_id [[thread_position_in_grid]],
    device uint& total_candles [[buffer(3)]]
) {
    // 1. Setup parameters
    int strategy_type = (int)params[scenario_id * 8 + 0];
    float p1 = params[scenario_id * 8 + 1]; // Param A
    float p2 = params[scenario_id * 8 + 2]; // Param B
    float p3 = params[scenario_id * 8 + 3]; // Param C
    int atr_period = (int)params[scenario_id * 8 + 4];
    float sl_mult = params[scenario_id * 8 + 5];
    float tp_mult = params[scenario_id * 8 + 6];
    float ts_mult = params[scenario_id * 8 + 7];

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
    float signal_ema = 0.0f; // Added for MACD Signal line
    float current_atr = 0.0f;
    float max_dd = 0.0f;
    float peak_equity = 1.0f;
    float total_wins_val = 0.0f;
    float total_losses_val = 0.0f;
    float sum_returns = 0.0f;
    float sum_sq_returns = 0.0f;
    int return_count = 0;

    // Logic Op state (for strategy_type 4)
    // p1: op_type (0: AND, 1: OR)
    // p2: sub_type1
    // p3: p2_1
    // p4 (atr_p): p3_1
    // p5 (sl_m): sub_type2
    // p6 (tp_m): p2_2
    // p7 (ts_m): p3_2
    // Need to use more buffers or wider param layout for complex logic? 
    // Let's use strategy_type 4 with a fixed layout for now.
    
    // Actually, let's keep it simple for now and use p2-p3 for first cond, p4-p5 for second? 
    // No, let's just use strategy_type 4 as "Logic AND/OR of two dynamic conditions"

    // 3. Main Loop
    for (uint i = 1; i < total_candles; i++) {
        const device Candle& c = data[i];
        const device Candle& prev_c = data[i-1];
        
        // Update Indicators
        float signal_val = 0.0f;
        
        if (strategy_type == 0) { // SMA Crossover
            float sma_fast = Indicators::calculate_sma(data, i, (int)p1);
            float sma_slow = Indicators::calculate_sma(data, i, (int)p2);
            if (sma_fast > sma_slow) signal_val = 1.0f;
            else if (sma_fast < sma_slow) signal_val = -1.0f;
        } 
        else if (strategy_type == 1) { // RSI
            float rsi = Indicators::update_rsi(c.close, prev_c.close, avg_gain, avg_loss, (int)p1, i);
            if (rsi < p3) signal_val = 1.0f;      // Use p3 as Oversold (e.g. 30)
            else if (rsi > p2) signal_val = -1.0f; // Use p2 as Overbought (e.g. 70)
            else signal_val = (float)pos; // Maintain
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
        else if (strategy_type == 3) {
            // Dynamic Generic (3)
            // p1: sub_type (0: Price > SMA, 1: Price > Max, 2: Price < Min, 3: Diff > 0)
            // p2: period
            // p3: offset/threshold
            if (p1 == 0.0f) {
                signal_val = Indicators::get_dynamic_signal(data, i, 0, p2, p3);
            } else if (p1 == 1.0f) {
                signal_val = Indicators::get_dynamic_signal(data, i, 1, p2, p3);
            } else if (p1 == 2.0f) {
                signal_val = Indicators::get_dynamic_signal(data, i, 2, p2, p3);
            } else if (p1 == 3.0f) {
                signal_val = Indicators::get_dynamic_signal(data, i, 3, p2, p3);
            } else if (p1 == 4.0f) {
                signal_val = Indicators::get_dynamic_signal(data, i, 4, p2, p3);
            } else if (p1 == 5.0f) {
                signal_val = Indicators::get_dynamic_signal(data, i, 5, p2, p3);
            } else if (p1 == 6.0f) {
                signal_val = Indicators::get_dynamic_signal(data, i, 6, p2, p3);
            }
        }
        else if (strategy_type == 4) {
             // Complex Logic (4)
             // Layout for type 4: [4, op_type, sub1, p2_1, p3_1, sub2, p2_2, p3_2]
             float s1_real = Indicators::get_dynamic_signal(data, i, (int)p2, p3, params[scenario_id * 8 + 4]);
             float s2_real = Indicators::get_dynamic_signal(data, i, (int)params[scenario_id * 8 + 5], params[scenario_id * 8 + 6], params[scenario_id * 8 + 7]);
             
             if (p1 == 0.0f) { // AND
                 signal_val = (s1_real > 0 && s2_real > 0) ? 1.0f : ((s1_real < 0 && s2_real < 0) ? -1.0f : 0.0f);
             } else { // OR
                 signal_val = (s1_real > 0 || s2_real > 0) ? 1.0f : ((s1_real < 0 || s2_real < 0) ? -1.0f : 0.0f);
             }
             
             // Fixed SL/TP for complex logic to free up param slots
             atr_period = 14;
             sl_mult = 1.5f;
             tp_mult = 3.0f;
             ts_mult = 2.0f;
         }
        else if (strategy_type == 5) { // Bollinger Bands
            float sma = Indicators::calculate_sma(data, i, (int)p1);
            float stddev = Indicators::calculate_stddev(data, i, (int)p1, sma);
            float upper = sma + (stddev * p2);
            float lower = sma - (stddev * p2);
            
            if (c.close < lower) signal_val = 1.0f;      // Oversold / Mean reversion buy
            else if (c.close > upper) signal_val = -1.0f; // Overbought / Mean reversion sell
            else signal_val = (float)pos;
        }

        current_atr = Indicators::update_atr(c, prev_c, current_atr, atr_period, i);

        // Strategy Execution
        if (pos == 0) {
            if (signal_val == 1.0f) {
                pos = 1;
                entry_price = c.close;
                sl_price = entry_price - (current_atr * sl_mult);
                tp_price = entry_price + (current_atr * tp_mult);
                trades++;
            } else if (signal_val == -1.0f) {
                pos = -1;
                entry_price = c.close;
                sl_price = entry_price + (current_atr * sl_mult);
                tp_price = entry_price - (current_atr * tp_mult);
                trades++;
            }
        } else {
            // Trailing Stop
            if (ts_mult > 0) {
                if (pos == 1) {
                    float new_sl = c.close - (current_atr * ts_mult);
                    if (new_sl > sl_price) sl_price = new_sl;
                } else {
                    float new_sl = c.close + (current_atr * ts_mult);
                    if (new_sl < sl_price) sl_price = new_sl;
                }
            }

            // Check SL/TP or Signal reversal
            bool exit = false;
            float pnl_pct = 0.0f;

            if (pos == 1) {
                if (c.low <= sl_price) { exit = true; pnl_pct = (sl_price / entry_price) - 1.0f; }
                else if (c.high >= tp_price) { exit = true; pnl_pct = (tp_price / entry_price) - 1.0f; }
                else if (signal_val <= 0.0f) { exit = true; pnl_pct = (c.close / entry_price) - 1.0f; }
            } else {
                if (c.high >= sl_price) { exit = true; pnl_pct = (entry_price / sl_price) - 1.0f; }
                else if (c.low <= tp_price) { exit = true; pnl_pct = (entry_price / tp_price) - 1.0f; }
                else if (signal_val >= 0.0f) { exit = true; pnl_pct = (entry_price / c.close) - 1.0f; }
            }

            if (exit) {
                equity *= (1.0f + pnl_pct);
                sum_returns += pnl_pct;
                sum_sq_returns += pnl_pct * pnl_pct;
                return_count++;
                
                if (pnl_pct > 0) {
                    wins++;
                    total_wins_val += pnl_pct;
                } else {
                    total_losses_val += abs(pnl_pct);
                }
                pos = 0;
                if (equity > peak_equity) peak_equity = equity;
                float dd = (peak_equity - equity) / peak_equity;
                if (dd > max_dd) max_dd = dd;
            }
        }
    }

    // 4. Finalize Results
    float sharpe = 0.0f;
    if (return_count > 1) {
        float mean = sum_returns / (float)return_count;
        float variance = (sum_sq_returns / (float)return_count) - (mean * mean);
        if (variance > 1e-9f) {
            sharpe = (mean / sqrt(variance)) * sqrt(252.0f); // Annualized (assuming daily-like frequency)
        }
    }

    results[scenario_id].total_return = equity - 1.0f;
    results[scenario_id].trade_count = trades;
    results[scenario_id].win_rate = (trades > 0) ? (float)wins / trades : 0.0f;
    results[scenario_id].max_drawdown = max_dd;
    results[scenario_id].profit_factor = (total_losses_val > 0) ? (total_wins_val / total_losses_val) : (total_wins_val > 0 ? 100.0f : 1.0f);
    results[scenario_id].sharpe_ratio = sharpe;
}
