"""Indicator generator module.

Core engine for generating robust trading indicators.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.indicators.technical import MACDIndicator, RSIIndicator, SMAIndicator
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.engine import MCConfig, MonteCarloEngine
from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


@dataclass
class GeneratorConfig:
    """Generator configuration."""

    max_iterations: int = 100000
    target_metrics: dict[str, float] = field(default_factory=dict)
    indicator_types: list[str] = field(default_factory=lambda: ["sma", "rsi", "macd", "dynamic"])
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
        "dynamic": {},
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

        logger.info(
            f"Starting indicator generation "
            f"(max {self.config.max_iterations} iterations)"
        )

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
            if self._progress_callback:
                status = f"Best MC rate: {best_mc_rate:.1%}"
                self._progress_callback(i + 1, self.config.max_iterations, status)

            # Early stopping if found good solution
            if self.config.early_stopping and best_mc_rate >= 0.95:
                logger.info(f"Early stopping: found solution at iteration {i + 1}")
                break

        elapsed = time.time() - start_time

        if self._progress_callback:
            status = f"Best MC rate: {best_mc_rate:.1%} [Finishing...]"
            self._progress_callback(self.config.max_iterations, self.config.max_iterations, status)

        # Get final metrics for best indicator
        final_metrics = {}
        if best_indicator:
            signals = best_indicator.generate_signals(data)
            final_metrics = self.metrics_calc.calculate_all(data, signals)

        if self._progress_callback:
            status = f"Best MC rate: {best_mc_rate:.1%} [Done]"
            self._progress_callback(self.config.max_iterations, self.config.max_iterations, status)

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

        indicator: BaseIndicator
        if ind_type == "sma":
            indicator = SMAIndicator()
        elif ind_type == "rsi":
            indicator = RSIIndicator()
        elif ind_type == "macd":
            indicator = MACDIndicator()
        elif ind_type == "dynamic":
            indicator = DynamicIndicator()
            code = self._generate_dynamic_code()
            indicator.set_parameter("source_code", code)
            return indicator
        else:
            indicator = SMAIndicator()

        # Set random parameters
        param_space = self.PARAM_SPACES.get(ind_type, {})
        for param_name, (min_val, max_val) in param_space.items():
            value = int(self.rng.integers(min_val, max_val + 1))
            indicator.set_parameter(param_name, value)

        return indicator

    def _generate_dynamic_code(self, depth: int = 0) -> str:
        """Generate a random valid Python expression for an indicator."""
        # Operands
        operands = ["data['close']", "data['open']", "data['high']", "data['low']", "data['volume']"]
        
        # Terminal condition (max depth or random stop)
        if depth >= 3 or (depth > 0 and self.rng.random() < 0.3):
            return self.rng.choice(operands)
        
        # Operators / Functions
        # 0: Binary Op, 1: Unary/Func
        op_type = self.rng.integers(0, 2)
        
        if op_type == 0:
            # Binary
            ops = ["+", "-", "*", "/", ">", "<"] # Include logical for signals? 
            # Note: logical operators return bool, usually used at top level or handled by DynamicIndicator
            # Let's keep it numeric mostly, maybe top level can be logical.
            # For simplicity, let's stick to arithmetic and let DynamicIndicator handle >0 logic 
            # UNLESS we explicitly want boolean signals.
            # The current DynamicIndicator maps >0 to 1, <0 to -1.
            # So (Close - MA) is good. 
            
            op = self.rng.choice(["+", "-", "*", "/"])
            left = self._generate_dynamic_code(depth + 1)
            right = self._generate_dynamic_code(depth + 1)
            return f"({left} {op} {right})"
            
        else:
            # Functions
            # rolling_mean, diff, shift
            
            func_type = self.rng.choice(["mean", "max", "min", "std", "diff", "shift"])
            period = self.rng.integers(3, 50)
            inner = self._generate_dynamic_code(depth + 1)
            
            if func_type == "mean":
                return f"{inner}.rolling({period}).mean()"
            elif func_type == "max":
                return f"{inner}.rolling({period}).max()"
            elif func_type == "min":
                return f"{inner}.rolling({period}).min()"
            elif func_type == "std":
                return f"{inner}.rolling({period}).std()"
            elif func_type == "diff":
                return f"{inner}.diff()" # Default diff 1
            elif func_type == "shift":
                return f"{inner}.shift({period})"
                
        return "data['close']" # Fallback

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
