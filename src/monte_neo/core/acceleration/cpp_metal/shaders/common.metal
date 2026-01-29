#include <metal_stdlib>
using namespace metal;

#ifndef COMMON_METAL
#define COMMON_METAL

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

#endif
