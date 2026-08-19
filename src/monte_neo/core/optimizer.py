"""Parameter optimizer module.

Optimizes indicator parameters using various strategies.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from monte_neo.utils.cache import load_calibration, save_calibration
from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    import pandas as pd

    from monte_neo.indicators.base import BaseIndicator
    from monte_neo.metrics.calculator import MetricsCalculator

logger = get_logger(__name__)


@dataclass
class OptimizationResult:
    """Optimization result."""

    best_params: dict
    best_score: float
    iterations: int
    history: list = field(default_factory=list)


class ParameterOptimizer:
    """Optimize indicator parameters."""

    def __init__(
        self,
        method: str = "random",
        max_iterations: int = 1000,
        random_seed: int | None = None,
    ) -> None:
        """Initialize optimizer.

        Args:
            method: Optimization method ('random', 'grid', 'genetic').
            max_iterations: Maximum iterations.
            random_seed: Random seed.
        """
        self.method = method
        self.max_iterations = max_iterations
        self.rng = np.random.default_rng(random_seed)

    def optimize(
        self,
        indicator: BaseIndicator,
        param_ranges: dict[str, tuple[int, int]],
        data: pd.DataFrame,
        metrics_calc: MetricsCalculator,
        objective: str = "sharpe_ratio",
        objective_func: Callable[[dict], float] | None = None,
    ) -> OptimizationResult:
        """Optimize indicator parameters.

        Args:
            indicator: Indicator to optimize.
            param_ranges: Parameter ranges {name: (min, max)}.
            data: OHLCV data.
            metrics_calc: Metrics calculator.
            objective: Metric to maximize.
            objective_func: Custom objective function.

        Returns:
            OptimizationResult with best parameters.
        """
        # Try to load from cache
        indicator_name = indicator.__class__.__name__
        if hasattr(indicator, "source_code"):
            # For dynamic indicators, use source code as part of the key
            indicator_name += f"_{hash(indicator.source_code)}"

        cached_params = load_calibration(indicator_name, data)
        if cached_params:
            logger.info(f"🚀 Using cached calibration for {indicator_name}")
            # We don't have the history/iterations, so we return a simplified result
            return OptimizationResult(
                best_params=cached_params,
                best_score=0.0,  # Unknown but presumably good
                iterations=0,
                history=[],
            )

        if self.method == "random":
            result = self._random_search(
                indicator, param_ranges, data, metrics_calc, objective, objective_func
            )
        elif self.method == "grid":
            result = self._grid_search(
                indicator, param_ranges, data, metrics_calc, objective, objective_func
            )
        elif self.method == "genetic":
            result = self._genetic_search(
                indicator, param_ranges, data, metrics_calc, objective, objective_func
            )
        else:
            raise ValueError(f"Unknown method: {self.method}")

        # Save to cache
        save_calibration(indicator_name, data, result.best_params)
        return result

    def _random_search(
        self,
        indicator: BaseIndicator,
        param_ranges: dict,
        data: pd.DataFrame,
        metrics_calc: MetricsCalculator,
        objective: str,
        objective_func: Callable | None,
    ) -> OptimizationResult:
        """Random search optimization."""
        best_params = {}
        best_score = float("-inf")
        history = []

        for i in range(self.max_iterations):
            # Generate random parameters
            params = {}
            for name, (min_val, max_val) in param_ranges.items():
                params[name] = int(self.rng.integers(min_val, max_val + 1))

            # Evaluate
            score = self._evaluate(
                indicator, params, data, metrics_calc, objective, objective_func
            )

            history.append({"iteration": i, "params": params, "score": score})

            if score > best_score:
                best_score = score
                best_params = dict(params)

        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            iterations=self.max_iterations,
            history=history,
        )

    def _grid_search(
        self,
        indicator: BaseIndicator,
        param_ranges: dict,
        data: pd.DataFrame,
        metrics_calc: MetricsCalculator,
        objective: str,
        objective_func: Callable | None,
    ) -> OptimizationResult:
        """Grid search optimization."""
        from itertools import product

        # Create grid
        grid_points = {}
        for name, (min_val, max_val) in param_ranges.items():
            step = max(1, (max_val - min_val) // 10)
            grid_points[name] = list(range(min_val, max_val + 1, step))

        # Search
        best_params = {}
        best_score = float("-inf")
        history = []
        iterations = 0

        for values in product(*grid_points.values()):
            params = dict(zip(grid_points.keys(), values))

            score = self._evaluate(
                indicator, params, data, metrics_calc, objective, objective_func
            )

            history.append({"iteration": iterations, "params": params, "score": score})
            iterations += 1

            if score > best_score:
                best_score = score
                best_params = dict(params)

            if iterations >= self.max_iterations:
                break

        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            iterations=iterations,
            history=history,
        )

    def _genetic_search(
        self,
        indicator: BaseIndicator,
        param_ranges: dict,
        data: pd.DataFrame,
        metrics_calc: MetricsCalculator,
        objective: str,
        objective_func: Callable | None,
    ) -> OptimizationResult:
        """Genetic algorithm optimization."""
        population_size = 50
        mutation_rate = 0.1
        elite_ratio = 0.2

        # Initialize population
        population = []
        for _ in range(population_size):
            params = {}
            for name, (min_val, max_val) in param_ranges.items():
                params[name] = int(self.rng.integers(min_val, max_val + 1))
            population.append(params)

        best_params = {}
        best_score = float("-inf")
        history = []
        generations = self.max_iterations // population_size

        for gen in range(generations):
            # Evaluate fitness
            fitness = []
            for params in population:
                score = self._evaluate(
                    indicator, params, data, metrics_calc, objective, objective_func
                )
                fitness.append((params, score))

            # Sort by fitness
            fitness.sort(key=lambda x: x[1], reverse=True)

            # Update best
            if fitness[0][1] > best_score:
                best_score = fitness[0][1]
                best_params = dict(fitness[0][0])

            history.append({"generation": gen, "best_score": best_score})

            # Selection and reproduction
            elite_count = int(population_size * elite_ratio)
            new_population = [f[0] for f in fitness[:elite_count]]

            while len(new_population) < population_size:
                # Tournament selection
                parent1 = self._tournament_select(fitness)
                parent2 = self._tournament_select(fitness)

                # Crossover and mutation
                child = self._crossover(parent1, parent2, param_ranges)
                child = self._mutate(child, param_ranges, mutation_rate)
                new_population.append(child)

            population = new_population

        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            iterations=generations * population_size,
            history=history,
        )

    def _evaluate(
        self,
        indicator: BaseIndicator,
        params: dict,
        data: pd.DataFrame,
        metrics_calc: MetricsCalculator,
        objective: str,
        objective_func: Callable | None,
    ) -> float:
        """Evaluate parameters."""
        indicator.set_parameters(params)
        signals = indicator.generate_signals(data)
        metrics = metrics_calc.calculate_all(data, signals)

        if objective_func:
            return objective_func(metrics)

        return metrics.get(objective, 0)

    def _tournament_select(self, fitness: list, k: int = 3) -> dict:
        """Tournament selection."""
        selected = self.rng.choice(
            len(fitness), size=min(k, len(fitness)), replace=False
        )
        best = max(selected, key=lambda i: fitness[i][1])
        return fitness[best][0]

    def _crossover(self, p1: dict, p2: dict, ranges: dict) -> dict:
        """Single-point crossover."""
        child = {}
        for name in ranges:
            child[name] = p1[name] if self.rng.random() < 0.5 else p2[name]
        return child

    def _mutate(self, params: dict, ranges: dict, rate: float) -> dict:
        """Mutation with given rate."""
        for name, (min_val, max_val) in ranges.items():
            if self.rng.random() < rate:
                params[name] = int(self.rng.integers(min_val, max_val + 1))
        return params
