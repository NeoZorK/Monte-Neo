#pragma once

#include <vector>
#include <string>
#include <memory>

namespace monte_neo {

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

// PIMPL to keep Metal/C++ headers clean and avoid Objective-C in public headers
class MetalBacktestBridge {
public:
    MetalBacktestBridge();
    ~MetalBacktestBridge();

    bool init();
    
    std::vector<BacktestResult> run_backtest(
        const std::vector<Candle>& data,
        const std::vector<float>& params,
        int n_scenarios
    );

private:
    class Impl;
    std::unique_ptr<Impl> pimpl;
};

} // namespace monte_neo
