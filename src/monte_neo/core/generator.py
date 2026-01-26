"""Indicator generator module.

Core engine for generating robust trading indicators.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from monte_neo.core.config import GeneratorConfig, GeneratorResult
from monte_neo.core.evolution import EvolutionEngine
from monte_neo.core.gpu_engine import MLXBacktestEngine
from monte_neo.indicators.base import BaseIndicator
from monte_neo.indicators.code_gen import CodeGenerator
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.indicators.technical import MACDIndicator, RSIIndicator, SMAIndicator
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.engine import MCConfig, MonteCarloEngine
from monte_neo.monte_carlo.workers import init_worker_data
from monte_neo.utils.logger import get_logger
from monte_neo.utils.parallel import ParallelExecutor

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


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
        """Generate a robust indicator.

        Args:
            data: OHLCV DataFrame for testing.

        Returns:
            GeneratorResult with best indicator.
        """
        start_time = time.time()
        best_indicator = None
        best_mc_rate = 0.0
        best_mc_details = {}
        iterations_tried = 0

        # Initialize persistent executor
        self.executor = ParallelExecutor(
            initializer=init_worker_data,
            initargs=(data,)
        )
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
        # Skip pre-generation for Block Bootstrap to use lazy evaluation (memory efficient)
        if not self.config.use_mc_block_bootstrap:
            try:
                temp_mc_config = MCConfig(
                    iterations=self.config.mc_iterations,
                    use_shuffling=self.config.use_mc_shuffling,
                    use_noise=self.config.use_mc_noise,
                    use_sensitivity=self.config.use_mc_sensitivity,
                    use_walk_forward=self.config.use_mc_walk_forward,
                    use_block_bootstrap=False, # Force false here as we handle it separately
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
                mc_scenarios = temp_engine.scenario_builder.generate(data)
                logger.debug(
                    f"Generated {len(mc_scenarios)} shared scenarios for this run"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to pre-generate scenarios: {e}. Will generate per candidate."
                )

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
                    gpu_results = self.gpu_engine.backtest_batch(
                        data,
                        batch_indicators,
                        executor=self.executor,
                        use_shared_data=True,
                        use_sl_tp=self.config.use_sl_tp,
                        sl_pct=self.config.stop_loss_pct,
                        tp_pct=self.config.take_profit_pct
                    )
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
                        full_metrics = self.metrics_calc.calculate_all(
                            data,
                            signals,
                            use_sl_tp=self.config.use_sl_tp,
                            sl_pct=self.config.stop_loss_pct,
                            tp_pct=self.config.take_profit_pct,
                        )

                        if not self._meets_basic_targets(full_metrics):
                            continue

                        if full_metrics.get("trade_count", 0) < self.config.min_trades:
                            continue

                        # 3. MC Validation
                        mc_result = self._run_mc_validation(
                            data,
                            indicator,
                            scenarios=mc_scenarios,
                        )
                        mc_pass_rate = mc_result.pass_rate

                        # Track candidates
                        if mc_pass_rate > 0.0:
                            self._candidates.append((indicator, mc_pass_rate))

                        # Update best
                        if mc_pass_rate > best_mc_rate:
                            best_mc_rate = mc_pass_rate
                            best_indicator = indicator
                            best_mc_details = {
                                "step_results": [
                                    {
                                        "method": r.method_name,
                                        "passed": r.passed,
                                        "rate": r.pass_rate,
                                        "advice": r.advice
                                    } for r in mc_result.step_results
                                ]
                            }
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
                        "Early stopping: found solution at iteration "
                        f"{batch_start + actual_batch_size}"
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
                    final_metrics = self.metrics_calc.calculate_all(
                        data, 
                        signals,
                        use_sl_tp=self.config.use_sl_tp,
                        sl_pct=self.config.stop_loss_pct,
                        tp_pct=self.config.take_profit_pct
                    )

                return GeneratorResult(
                    success=best_mc_rate >= 0.80,
                    indicator=best_indicator,
                    parameters=best_indicator.get_parameters(),
                    final_metrics=final_metrics,
                    mc_pass_rate=best_mc_rate,
                    mc_details=best_mc_details,
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
            logger.info(f"Starting evolutionary optimization on {len(self._candidates)} candidates...")
            try:
                # Filter candidates to only those with dynamic type for crossover to work best
                dynamic_candidates = [
                    c[0] for c in self._candidates 
                    if isinstance(c[0], DynamicIndicator)
                ]
                
                if len(dynamic_candidates) >= 2:
                    evolved_best = self._run_evolution(data, initial_population=dynamic_candidates)
                    if evolved_best:
                        # Check MC rate for evolved best
                        mc_result = self._run_mc_validation(data, evolved_best)
                        mc_rate = mc_result.pass_rate
                        
                        # Even if rate is not better, track it if it's decent
                        if mc_rate > 0:
                            self._candidates.append((evolved_best, mc_rate))
                            
                        if mc_rate > best_mc_rate:
                            best_mc_rate = mc_rate
                            best_indicator = evolved_best
                            best_mc_details = {
                                "step_results": [
                                    {
                                        "method": r.method_name,
                                        "passed": r.passed,
                                        "rate": r.pass_rate,
                                        "advice": r.advice
                                    } for r in mc_result.step_results
                                ]
                            }
                            logger.info(
                                f"Evolution found better indicator: {evolved_best.name} "
                                f"MC rate={mc_rate:.2%}"
                            )
            except Exception as e:
                logger.error(f"Evolutionary optimization failed: {e}")
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
            final_metrics = self.metrics_calc.calculate_all(
                data, 
                signals,
                use_sl_tp=self.config.use_sl_tp,
                sl_pct=self.config.stop_loss_pct,
                tp_pct=self.config.take_profit_pct
            )

        if self._progress_callback:
            status = f"Best MC rate: {best_mc_rate:.1%} [Done]"
            self._progress_callback(
                self.config.max_iterations, self.config.max_iterations, status
            )

        # Cleanup executor
        if self.executor:
            self.executor.__exit__(None, None, None)
            self.executor = None

        # Return result - success is based on threshold, but we ALWAYS return the best indicator if one was found
        return GeneratorResult(
            success=best_mc_rate >= 0.80,
            indicator=best_indicator,
            parameters=best_indicator.get_parameters() if best_indicator else {},
            final_metrics=final_metrics,
            mc_pass_rate=best_mc_rate,
            mc_details=best_mc_details,
            iterations_tried=iterations_tried,
            elapsed_time=elapsed,
            candidates_found=len(self._candidates),
        )

    def _mutate_indicator(self, indicator: BaseIndicator) -> BaseIndicator:
        """Mutate an indicator (wrapper for EvolutionEngine)."""
        # Create a temporary engine for mutation
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


    def _run_evolution(self, data: pd.DataFrame, initial_population: list[BaseIndicator] | None = None) -> BaseIndicator | None:
        """Run evolutionary optimization on candidates."""
        population = initial_population if initial_population is not None else [c[0] for c in self._candidates]

        evolution = EvolutionEngine(
            self.config,
            metrics_calc=self.metrics_calc,
            progress_callback=self._progress_callback
        )

        return evolution.run(data, population)

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
        use_sl_tp,
        sl_pct,
        tp_pct,
    ) = args

    # Quick pre-check
    signals = indicator.generate_signals(data)
    basic_metrics = metrics_calc.calculate_all(
        data, signals, use_sl_tp=use_sl_tp, sl_pct=sl_pct, tp_pct=tp_pct
    )

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
        use_sl_tp=use_sl_tp,
        sl_pct=sl_pct,
        tp_pct=tp_pct,
    )
    mc_engine = MonteCarloEngine(mc_config)
    result = mc_engine.run(data, indicator, metrics_calc, target_metrics)

    return indicator, result.pass_rate
