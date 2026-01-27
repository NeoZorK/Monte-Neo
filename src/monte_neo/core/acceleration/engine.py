"""
GPU Acceleration Engine (MLX).
"""

import time
from typing import Any

import mlx.core as mx
import numpy as np
import pandas as pd

from monte_neo.core.acceleration.indicators import MLXSMA, MLXCrossStrategy
from monte_neo.core.acceleration.tensor_ops import generate_noise_scenarios, generate_shuffle_scenarios, to_tensor


class GpuAccelerationEngine:
    """High-performance GPU engine."""
    
    def __init__(self, batch_size: int = 50000, precision: str = "float32", use_metal_cpp: bool = False):
        """
        Initialize GPU engine.
        
        Args:
            batch_size: Number of scenarios to process in each batch
            precision: 'float32', 'float16', 'float8_e4m3', or 'float8_e5m2'
            use_metal_cpp: Whether to use native Metal C++ shaders for float8
        """
        self.batch_size = batch_size
        self.precision = precision
        self.use_metal_cpp = use_metal_cpp
        
        # Initialize float8 encoder if needed
        self.float8_encoder = None
        self.metal_engine = None
        
        if precision.startswith("float8"):
            if use_metal_cpp:
                try:
                    from monte_neo.core.native.metal_engine import MetalFloat8Engine
                    self.metal_engine = MetalFloat8Engine()
                except (ImportError, RuntimeError) as e:
                    print(f"Warning: Could not initialize Metal engine: {e}. Falling back to Python encoder.")
                    self.use_metal_cpp = False
            
            if not self.use_metal_cpp:
                from monte_neo.core.acceleration.float8 import Float8Encoder
                format_type = "e4m3" if "e4m3" in precision else "e5m2"
                self.float8_encoder = Float8Encoder(format_type)
        
    def run_simulation(
        self,
        data: pd.DataFrame,
        mlx_strategy: Any,
        n_scenarios: int,
        method: str = "shuffling",
        seed: int = 42
    ) -> list[dict[str, Any]]:
        """
        Run generic simulation on GPU.
        
        Args:
            data: OHLCV DataFrame.
            mlx_strategy: Strategy object with generate_signals(close) method.
            n_scenarios: Number of scenarios.
            method: 'shuffling' or 'noise'.
        """
        # 1. To Tensor (Done once)
        tensors = to_tensor(data)
        close = tensors["close"]
        
        processed = 0
        all_results = []
        
        while processed < n_scenarios:
            current_batch = min(self.batch_size, n_scenarios - processed)
            
            # 2. Scenarios
            if self.use_metal_cpp and self.precision.startswith("float8"):
                # Use Metal C++ engine for float8 scenarios
                # First convert close to float8 using Metal
                close_np = np.array(close).astype(np.float32)
                if self.precision == "float8_e4m3":
                    close_f8 = self.metal_engine.encode_float32_to_e4m3(close_np)
                    # Note: For now we'll just use the metal engine to generate scenarios
                    # In a full implementation, we'd have a specialized generate_shuffle_scenarios_metal
                    scenarios_f8 = self.metal_engine.generate_scenarios_e4m3(close_f8, current_batch, seed=seed+processed)
                    scenarios_np = self.metal_engine.decode_e4m3_to_float32(scenarios_f8)
                    scenarios = mx.array(scenarios_np)
                else:
                    # Fallback to MLX for e5m2 if not fully implemented in Metal yet
                    scenarios = generate_shuffle_scenarios(close, current_batch, seed=seed+processed)
            elif method == "shuffling":
                scenarios = generate_shuffle_scenarios(close, current_batch, seed=seed+processed)
            elif method == "noise":
                scenarios = generate_noise_scenarios(close, current_batch, seed=seed+processed)
            else:
                # Default or error
                scenarios = generate_shuffle_scenarios(close, current_batch, seed=seed+processed)
            
            # 3. Signals
            signals = mlx_strategy.generate_signals(scenarios)
            
            # 4. Backtest
            returns = (scenarios[:, 1:] / scenarios[:, :-1]) - 1.0
            strat_returns = signals[:, :-1] * returns
            
            # Metrics
            equity = mx.exp(mx.cumsum(mx.log1p(strat_returns), axis=1))
            final_returns = equity[:, -1]
            
            # Max DD
            running_max = mx.cummax(equity, axis=1)
            max_dds = mx.max((running_max - equity) / running_max, axis=1)
            
            # Profit Factor
            wins = mx.where(strat_returns > 0, strat_returns, 0)
            losses = mx.where(strat_returns < 0, strat_returns, 0)
            gross_profit = mx.sum(wins, axis=1)
            gross_loss = mx.abs(mx.sum(losses, axis=1))
            profit_factor = mx.where(gross_loss > 0, gross_profit / gross_loss, 100.0)
            
            # Evaluate batch
            mx.eval(final_returns, max_dds, profit_factor)
            
            # Convert to numpy/list for result
            # We can't keep all results in GPU memory if N is huge?
            # Actually we just keep scalars.
            
            fr_np = np.array(final_returns)
            mdd_np = np.array(max_dds)
            pf_np = np.array(profit_factor)
            
            for i in range(current_batch):
                all_results.append({
                    "total_return": float(fr_np[i]) - 1.0,
                    "max_drawdown": float(mdd_np[i]),
                    "profit_factor": float(pf_np[i]),
                    "passed": bool(fr_np[i] > 1.0 and mdd_np[i] < 0.2), # Default criteria
                    "metrics": {
                        "total_return": float(fr_np[i]) - 1.0,
                        "max_drawdown": float(mdd_np[i]),
                        "profit_factor": float(pf_np[i]),
                    }
                })
            
            processed += current_batch
            
        return all_results

    def run_benchmark_simulation(self, data: pd.DataFrame, n_scenarios: int) -> dict:
        """
        Run a full simulation pipeline on GPU to benchmark performance.
        Pipeline:
        1. Data -> Tensor
        2. Shuffle Scenarios (N x T)
        3. Indicator Calc (SMA) -> Signals (N x T)
        4. Backtest (Vectorized)
        """
        start_time = time.time()
        
        # 1. To Tensor (Done once)
        tensors = to_tensor(data)
        close = tensors["close"]
        
        processed = 0
        
        while processed < n_scenarios:
            current_batch = min(self.batch_size, n_scenarios - processed)
            
            # 2. Scenarios
            scenarios = generate_shuffle_scenarios(close, current_batch)
            
            # 3. Signals
            sma = MLXSMA(10)
            strat = MLXCrossStrategy(sma)
            signals = strat.generate_signals(scenarios)
            
            # 4. Backtest
            returns = (scenarios[:, 1:] / scenarios[:, :-1]) - 1.0
            strat_returns = signals[:, :-1] * returns
            equity = mx.exp(mx.cumsum(mx.log1p(strat_returns), axis=1))
            final_return = equity[:, -1]
            
            # Force computation
            mx.eval(final_return)
            
            processed += current_batch
        
        elapsed = time.time() - start_time
        
        return {
            "elapsed": elapsed,
            "ops_per_sec": n_scenarios / elapsed,
            "scenarios_processed": n_scenarios
        }
