#include <vector>
#include <string>
#include <iostream>

struct NativeTradeResult {
    int entry_idx;
    int exit_idx;
    double entry_price;
    double exit_price;
    int direction;
    double pnl;
    double pnl_pct;
};

std::vector<NativeTradeResult> extract_trades_native(
    const std::vector<double>& prices,
    const std::vector<int>& signals
) {
    std::vector<NativeTradeResult> trades;
    int position = 0;
    int entry_idx = 0;
    double entry_price = 0.0;
    size_t n = signals.size();

    for (size_t i = 0; i < n; ++i) {
        int signal = signals[i];
        double price = prices[i];

        if (position == 0) {
            if (signal != 0) {
                position = signal;
                entry_idx = static_cast<int>(i);
                entry_price = price;
            }
        } else if (signal == -position) {
            double exit_price = price;
            double pnl = (exit_price - entry_price) * position;
            double pnl_pct = pnl / entry_price;

            trades.push_back({
                entry_idx,
                static_cast<int>(i),
                entry_price,
                exit_price,
                position,
                pnl,
                pnl_pct
            });

            position = 0;
        }
    }
    return trades;
}
