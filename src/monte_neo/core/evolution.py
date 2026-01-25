"""Evolutionary algorithm module."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator
from monte_neo.indicators.code_gen import CodeGenerator
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.utils.ast_utils import crossover_trees

if TYPE_CHECKING:
    from monte_neo.core.config import GeneratorConfig


class EvolutionEngine:
    """Evolutionary algorithm engine."""

    def __init__(
        self,
        config: GeneratorConfig,
        metrics_calc: MetricsCalculator | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None
    ):
        """Initialize engine.

        Args:
            config: Generator configuration.
            metrics_calc: Metrics calculator.
            progress_callback: Progress callback.
        """
        self.config = config
        self.metrics_calc = metrics_calc or MetricsCalculator()
        self.rng = np.random.default_rng()
        self.code_gen = CodeGenerator(self.rng)
        self.progress_callback = progress_callback

    def run(
        self,
        data: pd.DataFrame,
        initial_population: list[BaseIndicator]
    ) -> BaseIndicator | None:
        """Run evolutionary optimization.

        Args:
            data: OHLCV data.
            initial_population: Initial population.

        Returns:
            Best indicator found.
        """
        population: list[BaseIndicator] = list(initial_population)

        # Pad population if needed
        while len(population) < self.config.population_size:
            new_indicator = DynamicIndicator()
            new_indicator.set_parameter("source_code", self.code_gen.generate_code())
            population.append(new_indicator)

        for gen in range(self.config.generations):
            # Evaluate fitness
            fitness_scores: list[tuple[BaseIndicator, float]] = []
            for ind in population:
                try:
                    signals = ind.generate_signals(data)
                    metrics = self.metrics_calc.calculate_all(data, signals)

                    # Fitness function: Profit Factor * (1 - Max Drawdown)
                    pf = metrics.get("profit_factor", 0)
                    dd = metrics.get("max_drawdown", 1.0)
                    trades = metrics.get("trade_count", 0)

                    if trades < self.config.min_trades:
                        score = 0.0
                    else:
                        score = pf * (1.0 - dd)

                    fitness_scores.append((ind, score))
                except Exception:
                    fitness_scores.append((ind, 0.0))

            # Sort
            fitness_scores.sort(key=lambda x: x[1], reverse=True)
            best_gen_score = fitness_scores[0][1]

            if self.progress_callback:
                self.progress_callback(
                    gen + 1,
                    self.config.generations,
                    f"Evolution Gen {gen + 1}: Best Score {best_gen_score:.2f}",
                )

            # Selection (Elite + Tournament)
            elite_count = max(2, int(self.config.population_size * 0.1))
            new_pop: list[BaseIndicator] = [x[0] for x in fitness_scores[:elite_count]]

            while len(new_pop) < self.config.population_size:
                parent1 = self._tournament_select(fitness_scores)

                if self.rng.random() < self.config.crossover_rate:
                    parent2 = self._tournament_select(fitness_scores)
                    child = self._crossover_indicators(parent1, parent2)
                else:
                    child = self._mutate_indicator(parent1)

                new_pop.append(child)

            population = new_pop

        # Return the best found
        if not population:
            return None

        # Final evaluation
        final_scores: list[tuple[BaseIndicator, float]] = []
        for ind in population:
            try:
                signals = ind.generate_signals(data)
                metrics = self.metrics_calc.calculate_all(data, signals)
                pf = metrics.get("profit_factor", 0)
                dd = metrics.get("max_drawdown", 1.0)
                trades = metrics.get("trade_count", 0)
                score = pf * (1.0 - dd) if trades >= self.config.min_trades else 0.0
                final_scores.append((ind, score))
            except Exception:
                final_scores.append((ind, 0.0))

        final_scores.sort(key=lambda x: x[1], reverse=True)
        return final_scores[0][0] if final_scores[0][1] > 0 else None

    def _crossover_indicators(self, p1: BaseIndicator, p2: BaseIndicator) -> BaseIndicator:
        """Perform crossover."""
        if not isinstance(p1, DynamicIndicator) or not isinstance(p2, DynamicIndicator):
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
        if not isinstance(indicator, DynamicIndicator):
            return indicator

        code = indicator.get_parameters().get("source_code", "")
        if not code:
            return indicator

        new_code = code

        # Replace numbers
        def replace_num(match):
            val = int(match.group())
            change = self.rng.choice([-1, 1]) * max(1, int(val * 0.2))
            return str(max(1, val + change))

        if self.rng.random() < 0.5:
            new_code = re.sub(r"\b\d+\b", replace_num, code)
        else:
            op = self.rng.choice(["+", "-", "*"])
            operand = self.rng.choice(["data['close']", "data['volume']"])
            new_code = f"({code} {op} {operand})"

        new_ind = DynamicIndicator()
        new_ind.set_parameter("source_code", new_code)
        return new_ind
