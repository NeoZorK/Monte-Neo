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
    from monte_neo.utils.parallel import ParallelExecutor


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
        initial_population: list[BaseIndicator],
        executor: ParallelExecutor | None = None
    ) -> BaseIndicator | None:
        """Run evolutionary optimization."""
        population: list[BaseIndicator] = list(initial_population)
        best_overall: BaseIndicator | None = None
        best_fitness_overall: float = -float("inf")

        # Pad population if needed
        while len(population) < self.config.population_size:
            new_indicator = DynamicIndicator()
            new_indicator.set_parameter("source_code", self.code_gen.generate_code())
            population.append(new_indicator)

        try:
            for gen in range(self.config.generations):
                # Evaluate fitness
                fitness_scores: list[tuple[BaseIndicator, float]] = []

                # Use parallel execution for fitness evaluation to reach >2000 ops/s
                if executor:
                    from monte_neo.monte_carlo.workers import run_indicator_batch
                    n_workers = executor.n_workers
                    chunk_size = max(1, len(population) // n_workers)
                    chunks = [population[i : i + chunk_size] for i in range(0, len(population), chunk_size)]
                    tasks = [(chunk, None) for chunk in chunks]
                    batch_results = executor.map(run_indicator_batch, tasks)
                    raw_signals = []
                    for batch in batch_results:
                        raw_signals.extend(batch)
                else:
                    raw_signals = [ind.generate_signals_fast(data) for ind in population]

                # Prepare for Numba batch calculation
                signal_matrix = np.zeros((len(population), len(data)), dtype=np.int32)
                from monte_neo.core.gpu_scenarios import normalize_signal_array
                for i, sig in enumerate(raw_signals):
                    signal_matrix[i] = normalize_signal_array(sig, len(data)).astype(np.int32)

                batch_metrics_arr = self.metrics_calc.calculate_batch_fast(
                    data["close"].values,
                    data["high"].values,
                    data["low"].values,
                    signal_matrix,
                    use_sl_tp=self.config.use_sl_tp,
                    sl_pct=self.config.stop_loss_pct,
                    tp_pct=self.config.take_profit_pct
                )

                for i, ind in enumerate(population):
                    pf = batch_metrics_arr[i, 2]
                    dd = batch_metrics_arr[i, 1]
                    trades = int(batch_metrics_arr[i, 3])
                    fitness = pf * (1.0 - dd) if trades >= self.config.min_trades else 0.0
                    fitness_scores.append((ind, fitness))
                    
                    if fitness > best_fitness_overall:
                        best_fitness_overall = fitness
                        best_overall = ind

                # Sort population
                fitness_scores.sort(key=lambda x: x[1], reverse=True)
                
                if self.progress_callback:
                    status = f"Evolution Gen {gen + 1}/{self.config.generations} | Best Fitness: {fitness_scores[0][1]:.4f}"
                    self.progress_callback(gen + 1, self.config.generations, status)

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
        
        except KeyboardInterrupt:
            print("\nEvolution interrupted. Returning best found so far.")
            if best_overall is None and population:
                best_overall = population[0]

        return best_overall if best_overall else (population[0] if population else None)

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
