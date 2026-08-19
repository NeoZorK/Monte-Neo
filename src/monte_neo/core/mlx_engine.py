from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import mlx.core as mx
import numpy as np
import pandas as pd

from monte_neo.core.acceleration.engine import GpuAccelerationEngine
from monte_neo.core.gpu_lazy import backtest_lazy_scenarios as run_lazy_backtest
from monte_neo.core.gpu_scenarios import run_scenarios_backtest
from monte_neo.core.mlx_driver_utils import select_best_metal_driver, try_auto_compile_metal

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator
    from monte_neo.utils.parallel import ParallelExecutor

logger = logging.getLogger(__name__)

# Try to import the Metal bridge extension
try:
    from monte_neo.core.acceleration.cpp_metal.metal_engine import Driver, MetalBacktestBridge
    METAL_EXTENSION_AVAILABLE = True
except ImportError:
    METAL_EXTENSION_AVAILABLE = try_auto_compile_metal()
    if METAL_EXTENSION_AVAILABLE:
        from monte_neo.core.acceleration.cpp_metal.metal_engine import Driver, MetalBacktestBridge
    else:
        logger.warning("❌ Metal extension unavailable.")
        Driver = None
        MetalBacktestBridge = None

class MLXBacktestEngine:
    """GPU-accelerated backtesting engine using MLX."""

    def __init__(self, precision: str = "float32", metal_driver: str = "cpp", initial_capital: float = 100000.0, leverage: float = 1.0) -> None:
        self.precision = precision
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.pure_gpu_engine = GpuAccelerationEngine(precision=precision, metal_driver=metal_driver, initial_capital=initial_capital, leverage=leverage)
        self._data_prefetch_cache: dict[str, mx.array] = {}
        self._prefetch_lock = asyncio.Lock()
        self.native_bridge = None

        if METAL_EXTENSION_AVAILABLE:
            self.metal_driver = select_best_metal_driver(True, MetalBacktestBridge) if metal_driver == "auto" else metal_driver
            driver_map = {"cpp": Driver.CPP, "objc": Driver.OBJC, "swift": Driver.SWIFT}
            self.native_bridge = MetalBacktestBridge(driver_map.get(self.metal_driver, Driver.CPP))
            if not self.native_bridge.init():
                logger.warning(f"Failed to initialize Metal bridge with driver {self.metal_driver}")
                self.native_bridge = None
        else:
            self.metal_driver = "cpp" if metal_driver == "auto" else metal_driver

    def backtest_3d(self, **kwargs) -> list[list[dict[str, Any]]]:
        from monte_neo.core.mlx_3d_engine import backtest_3d_impl
        return backtest_3d_impl(self, **kwargs)

    def backtest_population_multi_scenario(self, **kwargs) -> np.ndarray:
        from monte_neo.core.mlx_3d_engine import backtest_population_multi_scenario_impl
        return backtest_population_multi_scenario_impl(self, **kwargs)

    async def prefetch_data(self, data: pd.DataFrame, key: str = "current") -> None:
        from monte_neo.core.acceleration.tensor_ops import to_tensor
        async with self._prefetch_lock:
            tensors = to_tensor(data)
            for k, v in tensors.items():
                mx.eval(v)
                self._data_prefetch_cache[f"{key}_{k}"] = v
        logger.debug(f"🚀 Data prefetched to GPU with key: {key}")

    def get_prefeteched_tensors(self, key: str = "current") -> dict[str, mx.array] | None:
        results = {k[len(key)+1:]: v for k, v in self._data_prefetch_cache.items() if k.startswith(f"{key}_")}
        return results if results else None

    def run_full_simulation(self, data: pd.DataFrame, indicator_or_list: BaseIndicator | list[BaseIndicator], n_scenarios: int, **kwargs) -> tuple[list[dict[str, Any]] | list[list[dict[str, Any]]], dict[str, float]]:
        from monte_neo.core.mlx_sim_engine import run_full_simulation_impl
        return run_full_simulation_impl(self, data, indicator_or_list, n_scenarios, **kwargs)

    def backtest_batch(self, **kwargs) -> list[dict[str, Any]]:
        from monte_neo.core.mlx_sim_engine import backtest_batch_impl
        return backtest_batch_impl(self, **kwargs)

    def backtest_scenarios(self, indicator: BaseIndicator, scenarios: list[pd.DataFrame], executor: ParallelExecutor | None = None,
                          use_sl_tp: bool = False, sl_pct: float = 0.0, tp_pct: float = 0.0) -> list[dict[str, Any]]:
        return run_scenarios_backtest(indicator, scenarios, executor, use_sl_tp=use_sl_tp, sl_pct=sl_pct, tp_pct=tp_pct)

    def backtest_lazy_scenarios(self, indicator: BaseIndicator, n_scenarios: int, executor: ParallelExecutor,
                               block_size: int | None = None, base_seed: int = 42, use_sl_tp: bool = False,
                               sl_pct: float = 0.0, tp_pct: float = 0.0) -> list[dict[str, Any]]:
        return run_lazy_backtest(indicator=indicator, n_scenarios=n_scenarios, executor=executor, block_size=block_size,
                                 base_seed=base_seed, use_sl_tp=use_sl_tp, sl_pct=sl_pct, tp_pct=tp_pct)
