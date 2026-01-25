from typing import Any

import mlx.core as mx
import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator
from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class MLXBacktestEngine:
    """GPU-accelerated backtesting engine using MLX."""

    def __init__(self):
        # M1 Pro usually has enough memory to hold large matrices
        pass

    def backtest_batch(
        self, data: pd.DataFrame, indicators: list[BaseIndicator]
    ) -> list[dict[str, Any]]:
        """Run multiple backtests simultaneously on the GPU.

        Args:
            data: OHLCV DataFrame.
            indicators: List of indicators to test.

        Returns:
            List of results for each indicator.
        """
        # 1. Prepare Price Data (Constant for all indicators)
        close_prices = mx.array(data["close"].to_numpy().astype(np.float32))

        # 2. Collect Signals into a Matrix (N_indicators x T_bars)
        # Note: Indicator signal generation is still CPU-bound or partially vectorized.
        # But we can stack the results for massive parallel equity calculation.
        signal_list = []
        for ind in indicators:
            signals = ind.generate_signals(data)
            signal_list.append(signals["signal"].to_numpy().astype(np.float32))

        # Shape: (N, T)
        signal_matrix = mx.array(np.stack(signal_list))

        # 3. Calculate Trades / Equity on GPU
        # Simple backtesting on GPU:
        # returns = signals[t-1] * (price[t] / price[t-1] - 1)

        # Shift prices for returns calculation
        # returns_pct = (close[1:] / close[:-1]) - 1
        returns_pct = (close_prices[1:] / close_prices[:-1]) - 1

        # Shift signals to avoid look-ahead bias (signals[t] affects return between t and t+1)
        # We align: signal[0] * returns_pct[0] (which is move from close[0] to close[1])
        strat_returns = signal_matrix[:, :-1] * returns_pct

        # Cumulative returns (Equity Curves)
        # log_returns = mx.log1p(strat_returns) # For precision, but simple cumprod is fine too
        equity_curves = mx.exp(
            mx.cumsum(mx.log1p(mx.clip(strat_returns, -0.999, 10.0)), axis=1)
        )

        # 4. Calculate Metrics on GPU
        # Final Return
        final_returns = equity_curves[:, -1]

        # Max Drawdown (Vectorized across all indicators)
        # running_max = mx.maximum.accumulate(equity_curves, axis=1) # type: ignore
        running_max = mx.cummax(equity_curves, axis=1)
        drawdowns = (running_max - equity_curves) / running_max
        max_drawdowns = mx.max(drawdowns, axis=1)

        # Profit Factor
        wins = mx.where(strat_returns > 0, strat_returns, 0)
        losses = mx.where(strat_returns < 0, strat_returns, 0)
        gross_profit = mx.sum(wins, axis=1)
        gross_loss = mx.abs(mx.sum(losses, axis=1))
        profit_factor = mx.where(gross_loss > 0, gross_profit / gross_loss, 100.0)

        # Sharp Ratio (simplified)
        mean_ret = mx.mean(strat_returns, axis=1)
        std_ret = mx.std(strat_returns, axis=1)
        sharpe = mx.where(
            std_ret > 0, mean_ret / std_ret * mx.sqrt(float(252)), 0.0
        )  # Assume daily for annualization

        # 5. Bring back to CPU
        results = []
        final_rets_np = np.array(final_returns)
        max_dds_np = np.array(max_drawdowns)
        sharpe_np = np.array(sharpe)
        pf_np = np.array(profit_factor)

        for i in range(len(indicators)):
            results.append(
                {
                    "total_return": float(final_rets_np[i]) - 1.0,
                    "max_drawdown": float(max_dds_np[i]),
                    "sharpe_ratio": float(sharpe_np[i]),
                    "profit_factor": float(pf_np[i]),
                    "success": bool(final_rets_np[i] > 1.0 and max_dds_np[i] < 0.2),
                    "metrics": {
                        "total_return": float(final_rets_np[i]) - 1.0,
                        "max_drawdown": float(max_dds_np[i]),
                        "sharpe_ratio": float(sharpe_np[i]),
                        "profit_factor": float(pf_np[i]),
                    },
                }
            )

        return results

    def backtest_scenarios(
        self, indicator: BaseIndicator, scenarios: list[pd.DataFrame]
    ) -> list[dict[str, Any]]:
        """Run one indicator across many data scenarios on GPU."""
        # 1. Prepare Returns Matrix (S_scenarios x T_bars)
        # Assuming OHLCV format, we pre-calculate returns for all scenarios
        returns_list = []
        for df in scenarios:
            rets = (df["close"].values[1:] / df["close"].values[:-1]) - 1
            returns_list.append(rets.astype(np.float32))

        # Handle variable lengths by padding with 0
        if not returns_list:
            return []
            
        max_len = max(len(r) for r in returns_list)
        padded_returns = []
        
        for r in returns_list:
            pad_width = max_len - len(r)
            if pad_width > 0:
                padded_returns.append(np.pad(r, (0, pad_width), "constant", constant_values=0))
            else:
                padded_returns.append(r)

        # Matrix: (S, T-1)
        returns_matrix = mx.array(np.stack(padded_returns))

        # 2. Get Signals (CPU for now, as indicators vary)
        # Note: If indicator is static, signals are same for many scenarios
        # (shuffling scenarios might need different signals depending on calculation).
        # We'll assume signals are per-scenario.
        signal_list = []
        for df in scenarios:
            sigs = indicator.generate_signals(df)
            # Signal length must match returns length (T-1)
            sig_vals = sigs["signal"].to_numpy()[:-1].astype(np.float32)
            
            # Pad signals if needed
            pad_width = max_len - len(sig_vals)
            if pad_width > 0:
                signal_list.append(np.pad(sig_vals, (0, pad_width), "constant", constant_values=0))
            else:
                signal_list.append(sig_vals)

        # Matrix: (S, T-1)
        signal_matrix = mx.array(np.stack(signal_list))

        # 3. Massive GPU calc
        strat_returns = signal_matrix * returns_matrix

        # Vectorized metrics
        equity_curves = mx.exp(
            mx.cumsum(mx.log1p(mx.clip(strat_returns, -0.9, 10.0)), axis=1)
        )

        final_rets = np.array(equity_curves[:, -1])

        # Max DD
        # running_max = mx.maximum.accumulate(equity_curves, axis=1) # type: ignore
        running_max = mx.cummax(equity_curves, axis=1)
        max_dds = np.array(mx.max((running_max - equity_curves) / running_max, axis=1))

        # Profit Factor
        wins = mx.where(strat_returns > 0, strat_returns, 0)
        losses = mx.where(strat_returns < 0, strat_returns, 0)
        gross_profit = mx.sum(wins, axis=1)
        gross_loss = mx.abs(mx.sum(losses, axis=1))
        profit_factor = np.array(mx.where(gross_loss > 0, gross_profit / gross_loss, 100.0))

        results = []
        for i in range(len(scenarios)):
            results.append(
                {
                    "total_return": float(final_rets[i]) - 1.0,
                    "max_drawdown": float(max_dds[i]),
                    "profit_factor": float(profit_factor[i]),
                    "passed": bool(final_rets[i] > 1.0 and max_dds[i] < 0.2),
                    "metrics": {
                        "total_return": float(final_rets[i]) - 1.0,
                        "max_drawdown": float(max_dds[i]),
                        "profit_factor": float(profit_factor[i]),
                    },
                }
            )
        return results
