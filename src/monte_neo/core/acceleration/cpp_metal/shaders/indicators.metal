#include <metal_stdlib>
#include "common.metal"

using namespace metal;

#ifndef INDICATORS_METAL
#define INDICATORS_METAL

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
    static float update_ema(float current_val, float prev_ema, int period) {
        float alpha = 2.0f / (float)(period + 1);
        return (current_val - prev_ema) * alpha + prev_ema;
    }

    // Relative Strength Index (RSI)
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
};

#endif
