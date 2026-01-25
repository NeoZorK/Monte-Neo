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
from monte_neo.core.gpu_engine import MLXBacktestEngine
from monte_neo.monte_carlo.engine import MCConfig, MonteCarloEngine
from monte_neo.utils.ast_utils import crossover_trees
from monte_neo.utils.logger import get_logger
from monte_neo.utils.parallel import ParallelExecutor

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


@dataclass
class GeneratorConfig:
    """Generator configuration."""

    max_iterations: int = 100000
    target_metrics: dict[str, float] = field(default_factory=dict)
    indicator_types: list[str] = field(
        default_factory=lambda: ["sma", "rsi", "macd", "dynamic"]
    )
    mc_iterations: int = 1000
    use_mc_shuffling: bool = True
    use_mc_noise: bool = True
    use_mc_sensitivity: bool = True
    use_mc_walk_forward: bool = True
    use_mc_block_bootstrap: bool = False
    early_stopping: bool = True
    min_trades: int = 30
    population_size: int = 50
    generations: int = 20
    mutation_rate: float = 0.3
    crossover_rate: float = 0.7


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
        """Set progress callback.

        Args:
            callback: Function(current, total, status).
        """
        self._progress_callback = callback

    def _run_mc_validation(
        self, 
        data: pd.DataFrame, 
        indicator: BaseIndicator,
        scenarios: list[pd.DataFrame] | None = None
    ) -> float:
        """Run Monte Carlo validation for a single indicator."""
        mc_config = MCConfig(
            iterations=self.config.mc_iterations,
            use_shuffling=self.config.use_mc_shuffling,
            use_noise=self.config.use_mc_noise,
            use_sensitivity=self.config.use_mc_sensitivity,
            use_walk_forward=self.config.use_mc_walk_forward,
            use_block_bootstrap=self.config.use_mc_block_bootstrap,
        )
        mc_engine = MonteCarloEngine(mc_config, executor=self.executor)
        
        result = mc_engine.run(
            data, 
            indicator, 
            self.metrics_calc, 
            self.config.target_metrics,
            existing_scenarios=scenarios
        )
        return result.pass_rate

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

        # Initialize persistent executor
        self.executor = ParallelExecutor()
        self.executor.__enter__()

        logger.info(
            f"Starting indicator generation "
            f"(max {self.config.max_iterations} iterations)"
        )

        batch_size = max(10, self.config.population_size)
        total_iterations = self.config.max_iterations

        logger.debug(f"Starting search with batch size {batch_size} (GPU-accelerated)")
        
        # Pre-generate MC scenarios for Common Random Numbers (fair comparison + speed)
        # We'll use a temporary engine to generate them once
        mc_scenarios = None
        try:
            temp_mc_config = MCConfig(
                iterations=self.config.mc_iterations,
                use_shuffling=self.config.use_mc_shuffling,
                use_noise=self.config.use_mc_noise,
                use_sensitivity=self.config.use_mc_sensitivity,
                use_walk_forward=self.config.use_mc_walk_forward,
                use_block_bootstrap=self.config.use_mc_block_bootstrap,
            )
            
            # Update progress bar status
            if self._progress_callback:
                self._progress_callback(
                    0, 
                    total_iterations, 
                    "Generating shared MC scenarios..."
                )
            
            logger.debug("Generating shared Monte Carlo scenarios...")
            # We need to access the internal generation method
            temp_engine = MonteCarloEngine(temp_mc_config)
            mc_scenarios = temp_engine._generate_scenarios(data)
            logger.debug(f"Generated {len(mc_scenarios)} shared scenarios for this run")
        except Exception as e:
            logger.warning(f"Failed to pre-generate scenarios: {e}. Will generate per candidate.")

        try:
            if self._progress_callback:
                self._progress_callback(0, total_iterations, "Starting search...")

            for batch_start in range(0, total_iterations, batch_size):
                actual_batch_size = min(batch_size, total_iterations - batch_start)

                # Generate candidates batch
                batch_indicators = [
                    self._generate_random_indicator() for _ in range(actual_batch_size)
                ]

                # GPU Backtest (Pre-filter)
                try:
                    gpu_results = self.gpu_engine.backtest_batch(data, batch_indicators)
                except Exception as e:
                    logger.warning(f"GPU Backtest failed: {e}. Skipping batch.")
                    gpu_results = []

                # Process results
                for i, result in enumerate(gpu_results):
                    iterations_tried += 1
                    indicator = batch_indicators[i]
                    metrics = result["metrics"]

                    # 1. GPU Pre-filter
                    if not self._meets_basic_targets(metrics):
                        continue

                    # 2. CPU Verification (Full Metrics)
                    try:
                        signals = indicator.generate_signals(data)
                        full_metrics = self.metrics_calc.calculate_all(data, signals)

                        if not self._meets_basic_targets(full_metrics):
                            continue

                        if full_metrics.get("trade_count", 0) < self.config.min_trades:
                            continue

                        # 3. MC Validation
                        mc_pass_rate = self._run_mc_validation(data, indicator, scenarios=mc_scenarios)

                        # Track candidates
                        if mc_pass_rate > 0.0:
                            self._candidates.append((indicator, mc_pass_rate))

                        # Update best
                        if mc_pass_rate > best_mc_rate:
                            best_mc_rate = mc_pass_rate
                            best_indicator = indicator
                            logger.info(
                                f"New best: {indicator.name} MC rate={mc_pass_rate:.2%}"
                            )

                    except Exception as e:
                        logger.warning(f"Error validating indicator: {e}")
                        continue

                # Progress callback
                if self._progress_callback:
                    current_iter = min(batch_start + batch_size, total_iterations)
                    elapsed = time.time() - start_time
                    ops_sec = current_iter / elapsed if elapsed > 0 else 0.0

                    # Simplified status update to avoid string processing overhead
                    speed_str = (
                        f"Speed: {ops_sec:.1f} op/s | "
                        f"{ops_sec * 60:.0f} op/m | "
                        f"{ops_sec * 3600:.0f} op/h"
                    )
                    status = f"Best MC rate: {best_mc_rate:.1%} | {speed_str}"
                    self._progress_callback(
                        current_iter,
                        total_iterations,
                        status,
                    )

                # Early stopping if found good solution
                if self.config.early_stopping and best_mc_rate >= 0.95:
                    logger.info(
                        f"Early stopping: found solution at iteration {batch_start + actual_batch_size}"
                    )
                    break
        
        except KeyboardInterrupt:
            # Cleanup executor immediately
            if self.executor:
                self.executor.__exit__(None, None, None)
                self.executor = None

            logger.info("Generation interrupted by user")
            from monte_neo.utils.console import console
            console.print("\n[yellow]Interrupted! Saving best result so far...[/]")
            if best_indicator:
                # Calculate metrics
                final_metrics = {}
                if best_indicator:
                    signals = best_indicator.generate_signals(data)
                    final_metrics = self.metrics_calc.calculate_all(data, signals)
                
                return GeneratorResult(
                    success=best_mc_rate >= 0.80,
                    indicator=best_indicator,
                    parameters=best_indicator.get_parameters(),
                    final_metrics=final_metrics,
                    mc_pass_rate=best_mc_rate,
                    iterations_tried=iterations_tried,
                    elapsed_time=time.time() - start_time,
                    candidates_found=len(self._candidates),
                )
            raise

        # Ensure main progress is done
        if self._progress_callback:
            status = f"Best MC rate: {best_mc_rate:.1%} [Search Complete]"
            self._progress_callback(
                total_iterations,
                total_iterations,
                status,
            )

        # If dynamic type is selected, we run evolutionary optimization at the end
        if "dynamic" in self.config.indicator_types and len(self._candidates) >= 2:
            logger.info("Starting evolutionary optimization on best candidates...")
            try:
                evolved_best = self._run_evolution(data)
                if evolved_best:
                    # Check MC rate for evolved best
                    mc_rate = self._run_mc_validation(data, evolved_best)
                    if mc_rate > best_mc_rate:
                        best_mc_rate = mc_rate
                        best_indicator = evolved_best
                        logger.info(
                            f"Evolution found better indicator: {evolved_best.name} "
                            f"MC rate={mc_rate:.2%}"
                        )
            except KeyboardInterrupt:
                logger.info("Evolutionary optimization interrupted by user")

        elapsed = time.time() - start_time

        if self._progress_callback:
            status = f"Best MC rate: {best_mc_rate:.1%} [Finishing...]"
            self._progress_callback(
                self.config.max_iterations, self.config.max_iterations, status
            )

        # Get final metrics for best indicator
        final_metrics = {}
        if best_indicator:
            signals = best_indicator.generate_signals(data)
            final_metrics = self.metrics_calc.calculate_all(data, signals)

        if self._progress_callback:
            status = f"Best MC rate: {best_mc_rate:.1%} [Done]"
            self._progress_callback(
                self.config.max_iterations, self.config.max_iterations, status
            )

        # Cleanup executor
        if self.executor:
            self.executor.__exit__(None, None, None)
            self.executor = None

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
        operands = [
            "data['close']",
            "data['open']",
            "data['high']",
            "data['low']",
            "data['volume']",
        ]

        # Terminal condition (max depth or random stop)
        if depth >= 3 or (depth > 0 and self.rng.random() < 0.3):
            return self.rng.choice(operands)

        # Operators / Functions
        # 0: Binary Op, 1: Unary/Func
        op_type = self.rng.integers(0, 2)

        if op_type == 0:
            # Binary
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
                return f"{inner}.diff()"  # Default diff 1
            elif func_type == "shift":
                return f"{inner}.shift({period})"

        return "data['close']"  # Fallback

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


    def _run_evolution(self, data: pd.DataFrame) -> BaseIndicator | None:
        """Run evolutionary optimization on candidates.

        Returns:
            Best indicator found during evolution or None.
        """

        population = [c[0] for c in self._candidates]
        # Pad population if needed
        while len(population) < self.config.population_size:
            population.append(self._generate_random_indicator())

        for gen in range(self.config.generations):
            # Evaluate fitness
            fitness_scores = []
            for ind in population:
                signals = ind.generate_signals(data)
                metrics = self.metrics_calc.calculate_all(data, signals)

                # Fitness function: Profit Factor * (1 - Max Drawdown) * Log(Trades)
                # This is simplified.
                pf = metrics.get("profit_factor", 0)
                dd = metrics.get("max_drawdown", 1.0)  # 0 to 1
                trades = metrics.get("trade_count", 0)

                if trades < self.config.min_trades:
                    score = 0.0
                else:
                    score = pf * (1.0 - dd)

                fitness_scores.append((ind, score))

            # Sort
            fitness_scores.sort(key=lambda x: x[1], reverse=True)
            best_gen_score = fitness_scores[0][1]

            if self._progress_callback:
                self._progress_callback(
                    gen + 1,
                    self.config.generations,
                    f"Evolution Gen {gen + 1}: Best Score {best_gen_score:.2f}",
                )

            # Selection (Elite + Tournament)
            elite_count = max(2, int(self.config.population_size * 0.1))
            new_pop = [x[0] for x in fitness_scores[:elite_count]]

            while len(new_pop) < self.config.population_size:
                # Tournament selection for parents
                parent1 = self._tournament_select(fitness_scores)

                if self.rng.random() < self.config.crossover_rate:
                    parent2 = self._tournament_select(fitness_scores)
                    child = self._crossover_indicators(parent1, parent2)
                else:
                    child = self._mutate_indicator(parent1)

                new_pop.append(child)

            population = new_pop

        # Return the best found in the last generation
        if not population:
            return None

        # Evaluate one last time to find the actual best
        final_scores = []
        for ind in population:
            signals = ind.generate_signals(data)
            metrics = self.metrics_calc.calculate_all(data, signals)
            pf = metrics.get("profit_factor", 0)
            dd = metrics.get("max_drawdown", 1.0)
            trades = metrics.get("trade_count", 0)
            score = pf * (1.0 - dd) if trades >= self.config.min_trades else 0.0
            final_scores.append((ind, score))

        final_scores.sort(key=lambda x: x[1], reverse=True)
        return final_scores[0][0] if final_scores[0][1] > 0 else None

    def _crossover_indicators(
        self, p1: BaseIndicator, p2: BaseIndicator
    ) -> BaseIndicator:
        """Perform crossover between two indicators."""
        if not isinstance(p1, DynamicIndicator) or not isinstance(p2, DynamicIndicator):
            # If not dynamic, just return a mutated version of p1
            return self._mutate_indicator(p1)

        code1 = p1.get_parameters().get("source_code", "data['close']")
        code2 = p2.get_parameters().get("source_code", "data['close']")

        new_code = crossover_trees(code1, code2)

        new_ind = DynamicIndicator()
        new_ind.set_parameter("source_code", new_code)
        return new_ind

    def _tournament_select(self, fitness: list, k: int = 3) -> BaseIndicator:
        indices = self.rng.integers(0, len(fitness), size=k)
        best_idx = max(indices, key=lambda i: fitness[i][1])
        return fitness[best_idx][0]

    def _mutate_indicator(self, indicator: BaseIndicator) -> BaseIndicator:
        """Mutate an indicator."""
        # Only mutate DynamicIndicator source code for now
        if not isinstance(indicator, DynamicIndicator):
            return indicator

        code = indicator.get_parameters().get("source_code", "")
        if not code:
            return indicator

        # Simple mutation: append or modify
        # For a robust implementation, we'd parse the AST.
        # Here we will just regenerate a part or parameter.
        # String manipulation is brittle, so let's try a simpler approach:
        # 50% chance to return a completely new random indicator (exploration)
        # 50% chance to wrap the current one in a new operation?

        # ACTUALLY, simpler approach for V1:
        # Just generate a new random code.
        # Real mutation needs AST.
        # Let's try to do string replacement of numbers at least?

        import re

        new_code = code

        # Replace numbers (parameters) with slightly different ones
        # Find all integers
        def replace_num(match):
            val = int(match.group())
            # +/- 20% or +/- 2
            change = self.rng.choice([-1, 1]) * max(1, int(val * 0.2))
            return str(max(1, val + change))  # Keep positive

        if self.rng.random() < 0.5:
            new_code = re.sub(r"\b\d+\b", replace_num, code)
        else:
            # Wrap in a new operation
            op = self.rng.choice(["+", "-", "*"])
            operand = self.rng.choice(["data['close']", "data['volume']"])
            new_code = f"({code} {op} {operand})"

        new_ind = DynamicIndicator()
        new_ind.set_parameter("source_code", new_code)
        return new_ind

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
        mc_factor = (
            10
            if any(
                [
                    self.config.use_mc_shuffling,
                    self.config.use_mc_noise,
                ]
            )
            else 2
        )

        total_seconds = time_per_iter * self.config.max_iterations * mc_factor
        return total_seconds / 60


def _search_worker(args: tuple) -> tuple[BaseIndicator | None, float]:
    """Worker for parallel indicator search."""
    (
        indicator,
        data,
        metrics_calc,
        target_metrics,
        mc_iterations,
        mc_shuffling,
        mc_noise,
        mc_sensitivity,
        mc_walk_forward,
        min_trades,
    ) = args

    # Quick pre-check
    signals = indicator.generate_signals(data)
    basic_metrics = metrics_calc.calculate_all(data, signals)

    # Skip if too few trades
    if basic_metrics.get("trade_count", 0) < min_trades:
        return None, 0.0

    # Skip if basic metrics don't meet targets
    # Inline check for performance
    for name, target in target_metrics.items():
        if name not in basic_metrics:
            continue
        actual = basic_metrics[name]
        if name in ["max_drawdown", "consecutive_losses"]:
            if actual > target:
                return None, 0.0
        else:
            if actual < target:
                return None, 0.0

    # Run Monte Carlo validation
    # Note: We need a static version of MC validation or use engine directly
    from monte_neo.monte_carlo.engine import MCConfig, MonteCarloEngine

    mc_config = MCConfig(
        iterations=mc_iterations,
        use_shuffling=mc_shuffling,
        use_noise=mc_noise,
        use_sensitivity=mc_sensitivity,
        use_walk_forward=mc_walk_forward,
    )
    mc_engine = MonteCarloEngine(mc_config)
    result = mc_engine.run(data, indicator, metrics_calc, target_metrics)

    return indicator, result.pass_rate
