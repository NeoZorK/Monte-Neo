"""Monte Carlo simulation engine.

Main engine for running Monte Carlo simulations with various methods.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from monte_neo.monte_carlo.scenarios import ScenarioBuilder
from monte_neo.monte_carlo.workers import init_worker_data, run_scenario_batch, run_single_scenario
from monte_neo.utils.logger import get_logger
from monte_neo.utils.parallel import ParallelExecutor

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator
    from monte_neo.metrics.calculator import MetricsCalculator

logger = get_logger(__name__)


@dataclass
class MCConfig:
    """Monte Carlo configuration."""

    iterations: int = 10000
    use_shuffling: bool = True
    use_noise: bool = True
    use_sensitivity: bool = True
    use_walk_forward: bool = True
    use_block_bootstrap: bool = False
    sensitivity_range: float = 0.10  # ±10%
    walk_forward_splits: int = 5
    n_workers: int | None = None
    random_seed: int | None = None


@dataclass
class MCResult:
    """Monte Carlo simulation result."""

    passed: bool
    pass_rate: float
    iterations_run: int
    elapsed_time: float
    metrics_summary: dict = field(default_factory=dict)
    detailed_results: list = field(default_factory=list)


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
    ) -> MCResult:
        """Run Monte Carlo simulation.

        Args:
            data: OHLCV DataFrame.
            indicator: Indicator to test.
            metrics_calc: Metrics calculator.
            target_metrics: Target metrics to achieve.
            existing_scenarios: Optional list of pre-generated scenarios.

        Returns:
            MCResult with simulation results.
        """
        start_time = time.time()
        passed_count = 0
        all_results = []

        # Generate test scenarios
        if self.config.use_block_bootstrap and existing_scenarios is None:
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
                    base_seed=self.config.random_seed or 42
                )

                # Transform results
                passed_count = sum(1 for r in results if r.get("passed", False))
                total = len(results)

                all_results = []
                for i, res in enumerate(results):
                    all_results.append({
                        "scenario_idx": i,
                        "passed": res.get("passed", False),
                        "metrics": res.get("metrics", {})
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
                    executor=self.executor
                )

                for i, res in enumerate(gpu_results):
                    # The GPU engine returns a dict with 'passed' and 'metrics'
                    if res["passed"]:
                        passed_count += 1
                    all_results.append(
                        {
                            "scenario_idx": i,
                            "passed": res["passed"],
                            "metrics": res[
                                "metrics"
                            ],  # Ensure metrics are correctly extracted
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
        from functools import partial

        # Use batching for better performance with multiprocessing
        executor = self.executor
        if executor is None:
            n_workers = self.config.n_workers
            executor = ParallelExecutor(n_workers=n_workers)

        n_workers = executor.n_workers

        # If scenarios are few or workers=1, run sequentially without batching overhead
        if total < 50 or n_workers == 1:
            worker_func = partial(
                run_single_scenario,
                indicator=indicator,
                metrics_calc=metrics_calc,
                target_metrics=target_metrics,
            )
            results = executor.map(worker_func, scenarios)

            # Process results
            for i, result in enumerate(results):
                if result is None:
                    continue
                meets_targets, metrics = result
                if meets_targets:
                    passed_count += 1
                all_results.append({
                    "scenario_idx": i,
                    "passed": meets_targets,
                    "metrics": metrics,
                })
        else:
            # Batch processing
            batch_size = max(10, total // (n_workers * 4))
            scenario_batches = [
                scenarios[i : i + batch_size]
                for i in range(0, total, batch_size)
            ]

            batch_worker = partial(
                run_scenario_batch,
                indicator=indicator,
                metrics_calc=metrics_calc,
                target_metrics=target_metrics,
            )

            batch_results_list = executor.map(batch_worker, scenario_batches)

            # Flatten results
            current_idx = 0
            for batch_res in batch_results_list:
                if not batch_res:
                    continue
                for meets_targets, metrics in batch_res:
                    if meets_targets:
                        passed_count += 1
                    all_results.append({
                        "scenario_idx": current_idx,
                        "passed": meets_targets,
                        "metrics": metrics,
                    })
                    current_idx += 1

        if self._progress_callback:
            self._progress_callback(total, total)

        return self._finalize_results(passed_count, total, all_results, start_time)

    def _finalize_results(
        self, passed_count: int, total: int, all_results: list, start_time: float
    ) -> MCResult:
        """Helper to package results."""
        elapsed = time.time() - start_time
        pass_rate = passed_count / total if total > 0 else 0

        logger.debug(f"MC complete: {passed_count}/{total} passed ({pass_rate:.1%})")

        return MCResult(
            passed=pass_rate >= 0.95,  # 95% pass rate required
            pass_rate=pass_rate,
            iterations_run=total,
            elapsed_time=elapsed,
            metrics_summary=self._summarize_metrics(all_results),
            detailed_results=all_results,
        )

    def _summarize_metrics(self, results: list[dict]) -> dict:
        """Summarize metrics across all scenarios.

        Args:
            results: List of scenario results.

        Returns:
            Summary statistics.
        """
        if not results:
            return {}

        # Collect all metric values
        metric_values: dict[str, list] = {}
        for result in results:
            for name, value in result.get("metrics", {}).items():
                if name not in metric_values:
                    metric_values[name] = []
                metric_values[name].append(value)

        # Calculate summary stats
        summary = {}
        for name, values in metric_values.items():
            arr = np.array(values)
            summary[name] = {
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "median": float(np.median(arr)),
                "p5": float(np.percentile(arr, 5)),
                "p95": float(np.percentile(arr, 95)),
            }

        return summary
