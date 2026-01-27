"""Monte Carlo simulation engine.

Main engine for running Monte Carlo simulations with various methods.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from monte_neo.monte_carlo.scenarios import ScenarioBuilder
from monte_neo.monte_carlo.types import MCConfig, MCResult
from monte_neo.monte_carlo.utils import summarize_metrics
from monte_neo.monte_carlo.workers import init_worker_data, run_scenario_batch, run_single_scenario
from monte_neo.utils.logger import get_logger
from monte_neo.utils.parallel import ParallelExecutor

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator
    from monte_neo.metrics.calculator import MetricsCalculator

logger = get_logger(__name__)

class MonteCarloEngine:
    """Monte Carlo simulation engine."""

    def __init__(
        self,
        config: MCConfig | None = None,
        executor: ParallelExecutor | None = None,
    ) -> None:
        """Initialize Monte Carlo engine.

        Args:
            config: Monte Carlo configuration.
            executor: Optional shared parallel executor.
        """
        self.config = config or MCConfig()
        self.executor = executor
        self.rng = np.random.default_rng(self.config.random_seed)

        # Initialize sub-modules
        self.scenario_builder = ScenarioBuilder(self.config)

        from monte_neo.core.gpu_engine import MLXBacktestEngine
        self.gpu_engine = MLXBacktestEngine()

        self._progress_callback: Callable[[int, int], None] | None = None

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        """Set progress callback function.

        Args:
            callback: Function(current, total) for progress updates.
        """
        self._progress_callback = callback

    def run(
        self,
        data: pd.DataFrame,
        indicator: BaseIndicator,
        metrics_calc: MetricsCalculator,
        target_metrics: dict[str, float],
        existing_scenarios: list[pd.DataFrame] | None = None,
        interactive: bool = True,
    ) -> MCResult:
        """Run Monte Carlo simulation.

        Args:
            data: OHLCV DataFrame.
            indicator: Indicator to test.
            metrics_calc: Metrics calculator.
            target_metrics: Target metrics to achieve.
            existing_scenarios: Optional list of pre-generated scenarios.
            interactive: Whether to ask for confirmation in sequential mode.

        Returns:
            MCResult with simulation results.
        """
        start_time = time.time()
        passed_count = 0
        all_results = []

        def _meets_targets(metrics: dict[str, float]) -> bool:
            for metric_name, target_value in target_metrics.items():
                if metric_name not in metrics:
                    continue
                actual = metrics[metric_name]
                if metric_name in ["max_drawdown", "consecutive_losses"]:
                    if actual > target_value:
                        return False
                else:
                    if actual < target_value:
                        return False
            return True

        if self.config.use_sequential:
            return self.run_sequential(data, indicator, metrics_calc, target_metrics, interactive=interactive)

        # Check for Pure GPU Acceleration (End-to-End on GPU)
        # Only for Shuffling method currently, and if indicator supports it.
        # This bypasses CPU scenario generation and data transfer overhead.
        has_mlx = indicator.to_mlx_representation() is not None
        only_shuffling = (
            (self.config.use_shuffling or not any([
                self.config.use_noise,
                self.config.use_sensitivity,
                self.config.use_walk_forward,
                self.config.use_block_bootstrap
            ]))
            and not self.config.use_noise
            and not self.config.use_sensitivity
            and not self.config.use_walk_forward
            and not self.config.use_block_bootstrap
        )

        if has_mlx and only_shuffling and existing_scenarios is None and self.config.iterations > 100:
            try:
                logger.info(f"🚀 Using High-Performance Pure GPU Engine for {self.config.iterations} iterations")
                results = self.gpu_engine.run_full_simulation(
                    data=data,
                    indicator=indicator,
                    n_scenarios=self.config.iterations,
                    method="shuffling",
                    seed=self.config.random_seed or 42,
                    use_sl_tp=self.config.use_sl_tp,
                    sl_pct=self.config.sl_pct,
                    tp_pct=self.config.tp_pct,
                )
                
                # Transform results to match MCResult format
                passed_count = sum(1 for r in results if _meets_targets(r.get("metrics", {})))
                total = len(results)
                
                all_results = []
                for i, res in enumerate(results):
                    metrics = res.get("metrics", {})
                    passed = _meets_targets(metrics)
                    all_results.append({
                        "scenario_idx": i,
                        "passed": passed,
                        "metrics": metrics
                    })

                if self._progress_callback:
                    self._progress_callback(total, total)

                return self._finalize_results(passed_count, total, all_results, start_time)
            
            except Exception as e:
                logger.warning(f"Pure GPU execution failed, falling back: {e}")
                # Fall through to standard methods
        
        # Generate test scenarios
        other_methods_enabled = (
            self.config.use_shuffling
            or self.config.use_noise
            or self.config.use_sensitivity
            or self.config.use_walk_forward
        )
        if (
            self.config.use_block_bootstrap
            and not other_methods_enabled
            and existing_scenarios is None
        ):
            # Lazy generation for Block Bootstrap to avoid memory overhead
            logger.debug(f"Running lazy Block Bootstrap with {self.config.iterations} iterations")

            # Ensure we have an executor with initialized data
            executor = self.executor
            should_shutdown = False

            if executor is None:
                # Create a local executor with data initialization
                executor = ParallelExecutor(
                    n_workers=self.config.n_workers,
                    initializer=init_worker_data,
                    initargs=(data,)
                )
                should_shutdown = True
                executor.__enter__()

            try:
                # Use GPU engine's lazy method
                results = self.gpu_engine.backtest_lazy_scenarios(
                    indicator,
                    self.config.iterations,
                    executor=executor,
                    block_size=None, # Auto-calculated
                    base_seed=self.config.random_seed or 42,
                    use_sl_tp=self.config.use_sl_tp,
                    sl_pct=self.config.sl_pct,
                    tp_pct=self.config.tp_pct,
                )

                # Transform results
                passed_count = sum(1 for r in results if _meets_targets(r.get("metrics", {})))
                total = len(results)

                all_results = []
                for i, res in enumerate(results):
                    metrics = res.get("metrics", {})
                    passed = _meets_targets(metrics)
                    all_results.append({
                        "scenario_idx": i,
                        "passed": passed,
                        "metrics": metrics
                    })

                if self._progress_callback:
                    self._progress_callback(total, total)

                return self._finalize_results(passed_count, total, all_results, start_time)

            finally:
                if should_shutdown and executor:
                    executor.__exit__(None, None, None)

        if existing_scenarios is not None:
            scenarios = existing_scenarios
        else:
            scenarios = self.scenario_builder.generate(data)
        total = len(scenarios)

        logger.debug(f"Running {total} Monte Carlo scenarios in parallel")

        # Prepare arguments for parallel execution
        # We use a helper function to avoid pickling issues with 'self' if possible,
        # but ProcessPoolExecutor usually handles methods if they are defined at module level.
        # Alternatively, we can use a standalone function.

        # Try GPU acceleration if many scenarios
        if len(scenarios) > 10:
            try:
                logger.debug(f"Offloading {total} scenarios to GPU (MLX)...")
                gpu_results = self.gpu_engine.backtest_scenarios(
                    indicator,
                    scenarios,
                    executor=self.executor,
                    use_sl_tp=self.config.use_sl_tp,
                    sl_pct=self.config.sl_pct,
                    tp_pct=self.config.tp_pct,
                )

                for i, res in enumerate(gpu_results):
                    # The GPU engine returns a dict with 'passed' and 'metrics'
                    metrics = res.get("metrics", {})
                    passed = _meets_targets(metrics)
                    if passed:
                        passed_count += 1
                    all_results.append(
                        {
                            "scenario_idx": i,
                            "passed": passed,
                            "metrics": metrics,
                        }
                    )

                if self._progress_callback:
                    self._progress_callback(total, total)

                return self._finalize_results(
                    passed_count, total, all_results, start_time
                )

            except Exception as e:
                logger.warning(f"GPU acceleration failed, falling back to CPU: {e}")

        # Fallback to CPU parallel execution
        cpu_results = self._run_cpu_parallel(scenarios, indicator, metrics_calc, target_metrics)
        passed_count += cpu_results["passed_count"]
        all_results.extend(cpu_results["all_results"])

        if self._progress_callback:
            self._progress_callback(total, total)

        return self._finalize_results(passed_count, total, all_results, start_time)

    def _run_cpu_parallel(
        self,
        scenarios: list[pd.DataFrame],
        indicator: BaseIndicator,
        metrics_calc: MetricsCalculator,
        target_metrics: dict[str, float],
    ) -> dict:
        """Run scenarios on CPU in parallel."""
        from functools import partial
        passed_count = 0
        all_results = []
        total = len(scenarios)

        executor = self.executor
        if executor is None:
            executor = ParallelExecutor(n_workers=self.config.n_workers)

        n_workers = executor.n_workers

        if total < 50 or n_workers == 1:
            worker_func = partial(
                run_single_scenario,
                indicator=indicator,
                metrics_calc=metrics_calc,
                target_metrics=target_metrics,
            )
            results = executor.map(worker_func, scenarios)

            for i, result in enumerate(results):
                if result is None: continue
                meets_targets, metrics = result
                if meets_targets: passed_count += 1
                all_results.append({"scenario_idx": i, "passed": meets_targets, "metrics": metrics})
        else:
            batch_size = max(10, total // (n_workers * 4))
            scenario_batches = [scenarios[i : i + batch_size] for i in range(0, total, batch_size)]
            batch_worker = partial(run_scenario_batch, indicator=indicator, metrics_calc=metrics_calc, target_metrics=target_metrics)
            batch_results_list = executor.map(batch_worker, scenario_batches)

            current_idx = 0
            for batch_res in batch_results_list:
                if not batch_res: continue
                for meets_targets, metrics in batch_res:
                    if meets_targets: passed_count += 1
                    all_results.append({"scenario_idx": current_idx, "passed": meets_targets, "metrics": metrics})
                    current_idx += 1

        return {"passed_count": passed_count, "all_results": all_results}

    def _finalize_results(
        self, passed_count: int, total: int, all_results: list, start_time: float
    ) -> MCResult:
        """Helper to package results."""
        elapsed = time.time() - start_time
        pass_rate = passed_count / total if total > 0 else 0

        logger.debug(f"MC complete: {passed_count}/{total} passed ({pass_rate:.1%})")

        return MCResult(
            passed=pass_rate >= self.config.pass_threshold,
            pass_rate=pass_rate,
            iterations_run=total,
            elapsed_time=elapsed,
            metrics_summary=summarize_metrics(all_results),
            detailed_results=all_results,
        )

    def run_sequential(
        self,
        data: pd.DataFrame,
        indicator: BaseIndicator,
        metrics_calc: MetricsCalculator,
        target_metrics: dict[str, float],
        interactive: bool = True,
    ) -> MCResult:
        """Run Monte Carlo simulation sequentially.

        Args:
            data: OHLCV DataFrame.
            indicator: Indicator to test.
            metrics_calc: Metrics calculator.
            target_metrics: Target metrics.
            interactive: Whether to ask for confirmation before each step.

        Returns:
            MCResult with sequential simulation results.
        """
        from monte_neo.monte_carlo.sequential import SequentialMCRunner
        runner = SequentialMCRunner(self)
        return runner.run(data, indicator, metrics_calc, target_metrics, interactive=interactive)
