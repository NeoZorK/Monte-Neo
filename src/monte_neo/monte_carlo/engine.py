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

from monte_neo.monte_carlo.noise import NoiseInjector
from monte_neo.monte_carlo.sensitivity import SensitivityAnalyzer
from monte_neo.monte_carlo.shuffler import DataShuffler
from monte_neo.monte_carlo.walk_forward import WalkForwardAnalyzer
from monte_neo.utils.logger import get_logger

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

    def __init__(self, config: MCConfig | None = None) -> None:
        """Initialize Monte Carlo engine.

        Args:
            config: Monte Carlo configuration.
        """
        self.config = config or MCConfig()
        self.rng = np.random.default_rng(self.config.random_seed)

        # Initialize sub-modules
        self.shuffler = DataShuffler(self.config.random_seed)
        self.noise_injector = NoiseInjector(self.config.random_seed)
        self.sensitivity = SensitivityAnalyzer()
        self.walk_forward = WalkForwardAnalyzer()

        self._progress_callback: Callable[[int, int], None] | None = None

    def set_progress_callback(
        self, callback: Callable[[int, int], None]
    ) -> None:
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
    ) -> MCResult:
        """Run Monte Carlo simulation.

        Args:
            data: OHLCV DataFrame.
            indicator: Indicator to test.
            metrics_calc: Metrics calculator.
            target_metrics: Target metrics to achieve.

        Returns:
            MCResult with simulation results.
        """
        start_time = time.time()
        passed_count = 0
        all_results = []

        # Generate test scenarios
        scenarios = self._generate_scenarios(data)
        total = len(scenarios)

        logger.info(f"Running {total} Monte Carlo scenarios")

        for i, scenario_data in enumerate(scenarios):
            # Generate signals
            signals = indicator.generate_signals(scenario_data)

            # Calculate metrics
            metrics = metrics_calc.calculate_all(scenario_data, signals)

            # Check if meets targets
            meets_targets = self._check_targets(metrics, target_metrics)

            if meets_targets:
                passed_count += 1

            all_results.append({
                "scenario_idx": i,
                "passed": meets_targets,
                "metrics": metrics,
            })

            # Progress callback
            if self._progress_callback and (i + 1) % 100 == 0:
                self._progress_callback(i + 1, total)

        elapsed = time.time() - start_time
        pass_rate = passed_count / total if total > 0 else 0

        logger.info(f"MC complete: {passed_count}/{total} passed ({pass_rate:.1%})")

        return MCResult(
            passed=pass_rate >= 0.95,  # 95% pass rate required
            pass_rate=pass_rate,
            iterations_run=total,
            elapsed_time=elapsed,
            metrics_summary=self._summarize_metrics(all_results),
            detailed_results=all_results,
        )

    def _generate_scenarios(self, data: pd.DataFrame) -> list[pd.DataFrame]:
        """Generate all test scenarios.

        Args:
            data: Base OHLCV data.

        Returns:
            List of scenario DataFrames.
        """
        scenarios = [data]  # Original data

        # Shuffled data
        if self.config.use_shuffling:
            scenarios.extend(
                self.shuffler.shuffle_returns(data, self.config.iterations // 4)
            )
            scenarios.extend(
                self.shuffler.shuffle_blocks(data, self.config.iterations // 4)
            )

        # Noisy data
        if self.config.use_noise:
            scenarios.extend(
                self.noise_injector.add_noise(data, self.config.iterations // 4)
            )

        # Limit total scenarios
        if len(scenarios) > self.config.iterations:
            scenarios = scenarios[: self.config.iterations]

        return scenarios

    def _check_targets(
        self,
        metrics: dict[str, float],
        targets: dict[str, float],
    ) -> bool:
        """Check if metrics meet targets.

        Args:
            metrics: Calculated metrics.
            targets: Target values.

        Returns:
            True if all targets are met.
        """
        for metric_name, target_value in targets.items():
            if metric_name not in metrics:
                continue

            actual = metrics[metric_name]

            # Handle metrics that should be less than target
            if metric_name in ["max_drawdown", "consecutive_losses"]:
                if actual > target_value:
                    return False
            else:
                if actual < target_value:
                    return False

        return True

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

    def estimate_time(self, data: pd.DataFrame, iterations: int) -> float:
        """Estimate time for simulation.

        Args:
            data: Sample data.
            iterations: Number of iterations.

        Returns:
            Estimated time in seconds.
        """
        # Run small sample
        sample_size = min(100, iterations)
        start = time.time()

        for _ in range(sample_size):
            _ = data.copy()  # Simulate minimal work

        elapsed = time.time() - start
        return (elapsed / sample_size) * iterations * 10  # 10x safety factor
