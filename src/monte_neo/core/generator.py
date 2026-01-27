"""Indicator generator module.

Core engine for generating robust trading indicators.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from monte_neo.core.config import GeneratorConfig, GeneratorResult
from monte_neo.core.evolution import EvolutionEngine
from monte_neo.core.generator_search import run_search
from monte_neo.core.generator_utils import PARAM_SPACES, estimate_time
from monte_neo.core.gpu_engine import MLXBacktestEngine
from monte_neo.indicators.base import BaseIndicator
from monte_neo.indicators.code_gen import CodeGenerator
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.indicators.technical import MACDIndicator, RSIIndicator, SMAIndicator
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.engine import MCConfig, MonteCarloEngine
from monte_neo.utils.logger import get_logger
from monte_neo.utils.parallel import ParallelExecutor

if TYPE_CHECKING:
    from monte_neo.monte_carlo.engine import MCResult

logger = get_logger(__name__)


class IndicatorGenerator:
    """Generate robust trading indicators."""

    def __init__(self, config: GeneratorConfig | None = None) -> None:
        """Initialize generator.

        Args:
            config: Generator configuration.
        """
        self.config = config or GeneratorConfig()
        self.rng = np.random.default_rng()
        self.metrics_calc = MetricsCalculator()
        self.gpu_engine = MLXBacktestEngine()
        self.executor: ParallelExecutor | None = None

        # State
        self.population: list[BaseIndicator] = []
        self._progress_callback: Callable[[int, int, str], None] | None = None
        self._candidates: list[tuple[BaseIndicator, float]] = []

    def set_progress_callback(
        self,
        callback: Callable[[int, int, str], None],
    ) -> None:
        """Set progress callback."""
        self._progress_callback = callback

    def _run_mc_validation(
        self,
        data: pd.DataFrame,
        indicator: BaseIndicator,
        scenarios: list[pd.DataFrame] | None = None
    ) -> MCResult:
        """Run Monte Carlo validation for a single indicator."""
        mc_config = MCConfig(
            iterations=self.config.mc_iterations,
            use_shuffling=self.config.use_mc_shuffling,
            use_noise=self.config.use_mc_noise,
            use_sensitivity=self.config.use_mc_sensitivity,
            use_walk_forward=self.config.use_mc_walk_forward,
            use_block_bootstrap=self.config.use_mc_block_bootstrap,
            use_sequential=self.config.use_sequential_mc,
            pass_threshold=self.config.mc_pass_threshold,
            use_sl_tp=self.config.use_sl_tp,
            sl_pct=self.config.stop_loss_pct,
            tp_pct=self.config.take_profit_pct,
            use_gpu=self.config.use_gpu,
            gpu_precision=self.config.gpu_precision,
            use_metal_cpp=self.config.use_metal_cpp,
        )
        mc_engine = MonteCarloEngine(mc_config, executor=self.executor)

        return mc_engine.run(
            data,
            indicator,
            self.metrics_calc,
            self.config.target_metrics,
            existing_scenarios=scenarios
        )

    def generate(self, data: pd.DataFrame) -> GeneratorResult:
        """Generate a robust indicator."""
        return run_search(self, data)

    def _mutate_indicator(self, indicator: BaseIndicator) -> BaseIndicator:
        """Mutate an indicator (wrapper for EvolutionEngine)."""
        evo = EvolutionEngine(self.config)
        return evo._mutate_indicator(indicator)

    def _generate_random_indicator(self) -> BaseIndicator:
        """Generate a random indicator with random parameters."""
        ind_type = self.rng.choice(self.config.indicator_types)
        indicator: BaseIndicator

        if ind_type == "sma":
            indicator = SMAIndicator()
        elif ind_type == "rsi":
            indicator = RSIIndicator()
        elif ind_type == "macd":
            indicator = MACDIndicator()
        elif ind_type == "dynamic":
            indicator = DynamicIndicator()
            code_gen = CodeGenerator(self.rng)
            code = code_gen.generate_code()
            indicator.set_parameter("source_code", code)
            return indicator
        else:
            indicator = SMAIndicator()

        # Set random parameters
        param_space = PARAM_SPACES.get(ind_type, {})
        for param_name, (min_val, max_val) in param_space.items():
            value = int(self.rng.integers(min_val, max_val + 1))
            indicator.set_parameter(param_name, value)

        return indicator

    def _meets_basic_targets(self, metrics: dict) -> bool:
        """Check if metrics meet basic targets."""
        for name, target in self.config.target_metrics.items():
            if name not in metrics:
                continue
            actual = metrics[name]
            if name in ["max_drawdown", "consecutive_losses"]:
                if actual > target:
                    return False
            else:
                if actual < target:
                    return False
        return True

    def _run_evolution(
        self,
        data: pd.DataFrame,
        initial_population: list[BaseIndicator] | None = None
    ) -> BaseIndicator | None:
        """Run evolutionary optimization on candidates."""
        population = initial_population if initial_population is not None else [c[0] for c in self._candidates]
        evolution = EvolutionEngine(
            self.config,
            metrics_calc=self.metrics_calc,
            progress_callback=self._progress_callback
        )
        return evolution.run(data, population, executor=self.executor)

    def estimate_time(self, data: pd.DataFrame) -> float:
        """Estimate generation time in minutes."""
        return estimate_time(self, data)
