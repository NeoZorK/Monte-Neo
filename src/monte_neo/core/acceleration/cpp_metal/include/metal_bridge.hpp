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
    float profit_factor;
    float sharpe_ratio;
};

// PIMPL to keep Metal/C++ headers clean and avoid Objective-C in public headers
class MetalBacktestBridge {
public:
    enum class Driver {
        CPP,
        OBJC,
        SWIFT
    };

    MetalBacktestBridge(Driver driver = Driver::CPP);
    ~MetalBacktestBridge();

    bool init();
    
    std::vector<BacktestResult> run_backtest(
        const std::vector<Candle>& data,
        const std::vector<float>& params,
        int n_scenarios
    );

    std::vector<BacktestResult> calculate_metrics(
        const float* close_prices,
        const float* high_prices,
        const float* low_prices,
        const int* signals,
        const float* params,
        int n_pop,
        int n_scenarios,
        int n_time,
        size_t close_size,
        size_t signals_size,
        size_t params_size
    );

    Driver get_driver() const { return driver_; }

private:
    class Impl;
    std::unique_ptr<Impl> pimpl;
    Driver driver_;
};

} // namespace monte_neo
