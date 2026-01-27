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
    static float update_rsi(float current_close, float prev_close, float &avg_gain, float &avg_loss, int period, int step) {
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
};

// --- Unified Backtest Kernel ---

kernel void backtest_kernel(
    const device Candle* data [[buffer(0)]],
    device BacktestResult* results [[buffer(1)]],
    const device float* params [[buffer(2)]],
    uint scenario_id [[thread_position_in_grid]],
    uint total_candles [[constant(0)]]
) {
    // 1. Setup parameters
    float p1 = params[scenario_id * 5 + 0]; // RSI Period
    float p2 = params[scenario_id * 5 + 1]; // ATR Period
    float sl_mult = params[scenario_id * 5 + 2]; // SL Multiplier (ATR)
    float tp_mult = params[scenario_id * 5 + 3]; // TP Multiplier (ATR)
    float ts_mult = params[scenario_id * 5 + 4]; // Trailing Stop Multiplier (ATR)

    // 2. State Management
    float equity = 1.0f;
    int pos = 0;
    float entry_price = 0.0f;
    float sl_price = 0.0f;
    float tp_price = 0.0f;
    float ts_activation_price = 0.0f;
    int trades = 0;
    int wins = 0;
    
    // Indicator state
    float avg_gain = 0.0f;
    float avg_loss = 0.0f;
    float current_atr = 0.0f;
    float max_dd = 0.0f;
    float peak_equity = 1.0f;

    // 3. Main Loop
    for (uint i = 1; i < total_candles; i++) {
        const device Candle& c = data[i];
        const device Candle& prev_c = data[i-1];
        
        // Update Indicators
        float rsi = Indicators::update_rsi(c.close, prev_c.close, avg_gain, avg_loss, (int)p1, i);
        current_atr = Indicators::update_atr(c, prev_c, current_atr, (int)p2, i);

        // Strategy Logic (e.g., RSI Mean Reversion)
        if (pos == 0) {
            if (rsi < 30.0f) { // Oversold -> Buy
                pos = 1;
                entry_price = c.close;
                sl_price = entry_price - (current_atr * sl_mult);
                tp_price = entry_price + (current_atr * tp_mult);
                trades++;
            } else if (rsi > 70.0f) { // Overbought -> Sell
                pos = -1;
                entry_price = c.close;
                sl_price = entry_price + (current_atr * sl_mult);
                tp_price = entry_price - (current_atr * tp_mult);
                trades++;
            }
        } else {
            // --- Trailing Stop Logic ---
            if (ts_mult > 0) {
                if (pos == 1) {
                    float new_sl = c.close - (current_atr * ts_mult);
                    if (new_sl > sl_price) sl_price = new_sl;
                } else {
                    float new_sl = c.close + (current_atr * ts_mult);
                    if (new_sl < sl_price) sl_price = new_sl;
                }
            }

            // Check SL/TP
            bool exit = false;
            float pnl_pct = 0.0f;

            if (pos == 1) {
                if (c.low <= sl_price) { exit = true; pnl_pct = (sl_price / entry_price) - 1.0f; }
                else if (c.high >= tp_price) { exit = true; pnl_pct = (tp_price / entry_price) - 1.0f; }
                else if (rsi > 50.0f) { exit = true; pnl_pct = (c.close / entry_price) - 1.0f; } // Exit at neutral
            } else {
                if (c.high >= sl_price) { exit = true; pnl_pct = (entry_price / sl_price) - 1.0f; }
                else if (c.low <= tp_price) { exit = true; pnl_pct = (entry_price / tp_price) - 1.0f; }
                else if (rsi < 50.0f) { exit = true; pnl_pct = (entry_price / c.close) - 1.0f; } // Exit at neutral
            }

            if (exit) {
                equity *= (1.0f + pnl_pct);
                if (pnl_pct > 0) wins++;
                pos = 0;
                
                // Drawdown tracking
                if (equity > peak_equity) peak_equity = equity;
                float dd = (peak_equity - equity) / peak_equity;
                if (dd > max_dd) max_dd = dd;
            }
        }
    }

    // 4. Finalize Results
    results[scenario_id].total_return = equity - 1.0f;
    results[scenario_id].trade_count = trades;
    results[scenario_id].win_rate = (trades > 0) ? (float)wins / trades : 0.0f;
    results[scenario_id].max_drawdown = max_dd;
}
