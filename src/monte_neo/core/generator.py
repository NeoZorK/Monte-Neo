"""Indicator generator module.

Core engine for generating robust trading indicators.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator
from monte_neo.indicators.technical import SMAIndicator, RSIIndicator, MACDIndicator
from monte_neo.monte_carlo.engine import MonteCarloEngine, MCConfig
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


@dataclass
class GeneratorConfig:
    """Generator configuration."""
    
    max_iterations: int = 100000
    target_metrics: dict[str, float] = field(default_factory=dict)
    indicator_types: list[str] = field(default_factory=lambda: ["sma", "rsi", "macd"])
    mc_iterations: int = 1000
    use_mc_shuffling: bool = True
    use_mc_noise: bool = True
    use_mc_sensitivity: bool = True
    use_mc_walk_forward: bool = True
    early_stopping: bool = True
    min_trades: int = 30


@dataclass
class GeneratorResult:
    """Generator result."""
    
    success: bool
    indicator: BaseIndicator | None
    parameters: dict
    final_metrics: dict
    mc_pass_rate: float
    iterations_tried: int
    elapsed_time: float
    candidates_found: int


class IndicatorGenerator:
    """Generate robust trading indicators."""

    # Parameter search spaces for each indicator type
    PARAM_SPACES = {
        "sma": {
            "fast_period": (5, 50),
            "slow_period": (20, 200),
        },
        "rsi": {
            "period": (5, 30),
            "overbought": (65, 85),
            "oversold": (15, 35),
        },
        "macd": {
            "fast": (8, 20),
            "slow": (20, 40),
            "signal": (5, 15),
        },
    }

    def __init__(self, config: GeneratorConfig | None = None) -> None:
        """Initialize generator.

        Args:
            config: Generator configuration.
        """
        self.config = config or GeneratorConfig()
        self.rng = np.random.default_rng()
        self.metrics_calc = MetricsCalculator()
        
        self._progress_callback: Callable[[int, int, str], None] | None = None
        self._candidates: list[tuple[BaseIndicator, float]] = []

    def set_progress_callback(
        self,
        callback: Callable[[int, int, str], None],
    ) -> None:
        """Set progress callback.

        Args:
            callback: Function(current, total, status).
        """
        self._progress_callback = callback

    def generate(self, data: pd.DataFrame) -> GeneratorResult:
        """Generate a robust indicator.

        Args:
            data: OHLCV DataFrame for testing.

        Returns:
            GeneratorResult with best indicator.
        """
        start_time = time.time()
        best_indicator = None
        best_mc_rate = 0.0
        iterations_tried = 0

        logger.info(f"Starting indicator generation (max {self.config.max_iterations} iterations)")

        for i in range(self.config.max_iterations):
            iterations_tried = i + 1
            
            # Generate random indicator
            indicator = self._generate_random_indicator()
            
            # Quick pre-check
            signals = indicator.generate_signals(data)
            basic_metrics = self.metrics_calc.calculate_all(data, signals)
            
            # Skip if too few trades
            if basic_metrics.get("trade_count", 0) < self.config.min_trades:
                continue
            
            # Skip if basic metrics don't meet targets
            if not self._meets_basic_targets(basic_metrics):
                continue

            # Run Monte Carlo validation
            mc_rate = self._run_mc_validation(data, indicator)
            
            # Track candidates
            if mc_rate > 0.5:
                self._candidates.append((indicator, mc_rate))
            
            # Update best
            if mc_rate > best_mc_rate:
                best_mc_rate = mc_rate
                best_indicator = indicator
                logger.info(f"New best: {indicator.name} MC rate={mc_rate:.2%}")

            # Progress callback
            if self._progress_callback and (i + 1) % 100 == 0:
                status = f"Best MC rate: {best_mc_rate:.1%}"
                self._progress_callback(i + 1, self.config.max_iterations, status)

            # Early stopping if found good solution
            if self.config.early_stopping and best_mc_rate >= 0.95:
                logger.info(f"Early stopping: found solution at iteration {i + 1}")
                break

        elapsed = time.time() - start_time
        
        # Get final metrics for best indicator
        final_metrics = {}
        if best_indicator:
            signals = best_indicator.generate_signals(data)
            final_metrics = self.metrics_calc.calculate_all(data, signals)

        return GeneratorResult(
            success=best_mc_rate >= 0.80,
            indicator=best_indicator,
            parameters=best_indicator.get_parameters() if best_indicator else {},
            final_metrics=final_metrics,
            mc_pass_rate=best_mc_rate,
            iterations_tried=iterations_tried,
            elapsed_time=elapsed,
            candidates_found=len(self._candidates),
        )

    def _generate_random_indicator(self) -> BaseIndicator:
        """Generate a random indicator with random parameters."""
        ind_type = self.rng.choice(self.config.indicator_types)
        
        if ind_type == "sma":
            indicator = SMAIndicator()
        elif ind_type == "rsi":
            indicator = RSIIndicator()
        elif ind_type == "macd":
            indicator = MACDIndicator()
        else:
            indicator = SMAIndicator()

        # Set random parameters
        param_space = self.PARAM_SPACES.get(ind_type, {})
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

    def _run_mc_validation(
        self,
        data: pd.DataFrame,
        indicator: BaseIndicator,
    ) -> float:
        """Run Monte Carlo validation."""
        mc_config = MCConfig(
            iterations=self.config.mc_iterations,
            use_shuffling=self.config.use_mc_shuffling,
            use_noise=self.config.use_mc_noise,
            use_sensitivity=self.config.use_mc_sensitivity,
            use_walk_forward=self.config.use_mc_walk_forward,
        )
        
        mc_engine = MonteCarloEngine(mc_config)
        result = mc_engine.run(
            data, indicator, self.metrics_calc, self.config.target_metrics
        )
        
        return result.pass_rate

    def estimate_time(self, data: pd.DataFrame) -> float:
        """Estimate generation time in minutes.

        Args:
            data: Sample data.

        Returns:
            Estimated time in minutes.
        """
        # Run small sample
        sample_iterations = 10
        start = time.time()
        
        for _ in range(sample_iterations):
            indicator = self._generate_random_indicator()
            signals = indicator.generate_signals(data)
            _ = self.metrics_calc.calculate_all(data, signals)
        
        elapsed = time.time() - start
        time_per_iter = elapsed / sample_iterations
        
        # Account for MC validation (~10x slower)
        mc_factor = 10 if any([
            self.config.use_mc_shuffling,
            self.config.use_mc_noise,
        ]) else 2
        
        total_seconds = time_per_iter * self.config.max_iterations * mc_factor
        return total_seconds / 60
