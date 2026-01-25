from typing import Any

import mlx.core as mx
import numpy as np
import pandas as pd

from monte_neo.utils.parallel import ParallelExecutor
from monte_neo.utils.logger import get_logger
from monte_neo.monte_carlo.workers import (
    run_block_bootstrap_scenario, 
    _generate_signals_wrapper, 
    _generate_lazy_scenario_wrapper
)

logger = get_logger(__name__)


class MLXBacktestEngine:
    """GPU-accelerated backtesting engine using MLX."""

    def __init__(self):
        # M1 Pro usually has enough memory to hold large matrices
        pass


    def backtest_batch(
        self, 
        data: pd.DataFrame, 
        indicators: list[BaseIndicator],
        executor: ParallelExecutor | None = None
    ) -> list[dict[str, Any]]:
        """Run multiple backtests simultaneously on the GPU.

        Args:
            data: OHLCV DataFrame.
            indicators: List of indicators to test.
            executor: Optional shared parallel executor for signal generation.

        Returns:
            List of results for each indicator.
        """
        # 1. Prepare Price Data (Constant for all indicators)
        close_prices = mx.array(data["close"].to_numpy().astype(np.float32))

        # 2. Collect Signals into a Matrix (N_indicators x T_bars)
        # Note: Indicator signal generation is still CPU-bound or partially vectorized.
        # But we can stack the results for massive parallel equity calculation.
        signal_list = []
        
        # Prepare args for parallel execution
        # Each task is (indicator, data)
        # Since data is same for all, we might want to avoid pickling it N times if it's huge.
        # But for parallel execution, arguments must be pickled.
        # ParallelExecutor uses process pool, so pickling is unavoidable.
        tasks = [(ind, data) for ind in indicators]
        
        # Parallelize signal generation if batch size is large enough
        if len(indicators) > 5:
            if executor is None:
                local_executor = ParallelExecutor()
                raw_signals = local_executor.map(_generate_signals_wrapper, tasks)
            else:
                raw_signals = executor.map(_generate_signals_wrapper, tasks)
        else:
            # Serial execution for small batches
            raw_signals = []
            for ind in indicators:
                try:
                    raw_signals.append(ind.generate_signals(data))
                except Exception:
                    raw_signals.append(None)
                    
        # Process results
        for sigs in raw_signals:
            if sigs is None:
                # Handle error case with zero signal
                # Assuming data length
                signal_list.append(np.zeros(len(data), dtype=np.float32))
            else:
                signal_list.append(sigs)

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

    def backtest_lazy_scenarios(
        self,
        indicator: BaseIndicator,
        n_scenarios: int,
        executor: ParallelExecutor,
        block_size: int | None = None,
        base_seed: int = 42
    ) -> list[dict[str, Any]]:
        """Run backtest with lazy scenario generation (Block Bootstrap)."""
        # 1. Generate Signals & Returns in Parallel
        seeds = [base_seed + i for i in range(n_scenarios)]
        tasks = [(indicator, seed, block_size) for seed in seeds]
        
        raw_results = executor.map(_generate_lazy_scenario_wrapper, tasks)
        
        signal_list = []
        returns_list = []
        
        for res in raw_results:
            if res is None:
                continue
            
            sigs, rets = res
            # Ensure 1D array and slice
            sig_vals = sigs
            if len(sig_vals.shape) > 1:
                sig_vals = sig_vals.flatten()
            sig_vals = sig_vals[:-1].astype(np.float32)
            
            signal_list.append(sig_vals)
            returns_list.append(rets)
            
        if not signal_list:
            return []
            
        max_len = max(len(s) for s in signal_list)
        
        padded_signals = []
        padded_returns = []
        
        for s, r in zip(signal_list, returns_list):
            pad_width = max_len - len(s)
            if pad_width > 0:
                padded_signals.append(np.pad(s, (0, pad_width), "constant", constant_values=0))
                padded_returns.append(np.pad(r, (0, pad_width), "constant", constant_values=0))
            else:
                padded_signals.append(s)
                padded_returns.append(r)
                
        signal_matrix = mx.array(np.stack(padded_signals))
        returns_matrix = mx.array(np.stack(padded_returns))
        
        # 2. GPU Calc
        strat_returns = signal_matrix * returns_matrix
        
        equity_curves = mx.exp(
            mx.cumsum(mx.log1p(mx.clip(strat_returns, -0.9, 10.0)), axis=1)
        )
        
        final_rets = np.array(equity_curves[:, -1])
        
        running_max = mx.cummax(equity_curves, axis=1)
        max_dds = np.array(mx.max((running_max - equity_curves) / running_max, axis=1))
        
        wins = mx.where(strat_returns > 0, strat_returns, 0)
        losses = mx.where(strat_returns < 0, strat_returns, 0)
        gross_profit = mx.sum(wins, axis=1)
        gross_loss = mx.abs(mx.sum(losses, axis=1))
        profit_factor = np.array(mx.where(gross_loss > 0, gross_profit / gross_loss, 100.0))
        
        results = []
        for i in range(len(signal_list)):
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

    def backtest_scenarios(
        self, 
        indicator: BaseIndicator, 
        scenarios: list[pd.DataFrame],
        executor: ParallelExecutor | None = None
    ) -> list[dict[str, Any]]:
        """Run one indicator across many data scenarios on GPU.
        
        Args:
            indicator: Indicator to test.
            scenarios: List of data scenarios.
            executor: Optional shared parallel executor for signal generation.
        """
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

        # 2. Get Signals (CPU parallelized)
        # We use ParallelExecutor to speed up signal generation for many scenarios
        signal_list = []
        
        # Prepare args for parallel execution
        # (indicator is pickleable usually)
        tasks = [(indicator, df) for df in scenarios]
        
        # Use ProcessPoolExecutor for CPU-bound signal generation
        # Adjust n_workers as needed, default is usually fine
        # NOTE: Parallelizing might have overhead for small DataFrames. 
        # But for 1000 scenarios, it should help.
        
        # If scenarios are few, do serial
        if len(scenarios) < 50:
             for df in scenarios:
                sigs = indicator.generate_signals(df)
                sig_vals = sigs["signal"].to_numpy()[:-1].astype(np.float32)
                
                # Pad signals if needed
                pad_width = max_len - len(sig_vals)
                if pad_width > 0:
                    signal_list.append(np.pad(sig_vals, (0, pad_width), "constant", constant_values=0))
                else:
                    signal_list.append(sig_vals)
        else:
            # Parallel execution
            if executor is None:
                local_executor = ParallelExecutor()
                # Map returns results in order
                raw_signals = local_executor.map(_generate_signals_wrapper, tasks)
            else:
                # Use shared executor
                raw_signals = executor.map(_generate_signals_wrapper, tasks)
            
            for i, sigs in enumerate(raw_signals):
                if sigs is None: # Error case
                     # Fill with zeros or handle error
                     sig_vals = np.zeros(max_len, dtype=np.float32)
                else:
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
