"""AI-Driven Evolutionary Engine.

Advanced evolutionary optimization with symbolic regression and heuristic-based mutation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator
from monte_neo.indicators.code_gen import CodeGenerator
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class EvolutionStats:
    generation: int
    best_fitness: float
    avg_fitness: float
    diversity_score: float

class AIEvolutionEngine:
    """Advanced evolution engine with AI-inspired heuristics."""

    def __init__(
        self,
        population_size: int = 100,
        mutation_rate: float = 0.2,
        crossover_rate: float = 0.8,
        metrics_calc: MetricsCalculator | None = None
    ):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.metrics_calc = metrics_calc or MetricsCalculator()
        self.rng = np.random.default_rng()
        self.code_gen = CodeGenerator(self.rng)
        
        # Heuristics: Map weaknesses to potential fixes
        self.heuristics = {
            "high_drawdown": ["trend_filter", "volatility_exit"],
            "low_winrate": ["mean_reversion_filter", "tighter_sl"],
            "instability": ["smoothing", "higher_timeframe_confirmation"]
        }

    def evolve(self, data: pd.DataFrame, target_metrics: dict[str, float], generations: int = 10) -> BaseIndicator:
        """Runs the AI-driven evolution process."""
        population = self._initialize_population()
        
        for gen in range(generations):
            fitness_scores = self._evaluate_population(population, data, target_metrics)
            
            # Sort by fitness
            population = [p for p, f in sorted(zip(population, fitness_scores), key=lambda x: x[1], reverse=True)]
            best_fitness = fitness_scores[0]
            
            logger.info(f"Gen {gen}: Best Fitness = {best_fitness:.4f}")
            
            # Selection & Breeding
            new_population = population[:int(self.population_size * 0.1)] # Elitism 10%
            
            while len(new_population) < self.population_size:
                if self.rng.random() < self.crossover_rate:
                    parent1, parent2 = self.rng.choice(population[:20], size=2)
                    child = self._crossover(parent1, parent2)
                else:
                    parent = self.rng.choice(population[:20])
                    child = self._mutate(parent)
                new_population.append(child)
            
            population = new_population

        return population[0]

    def _initialize_population(self) -> list[BaseIndicator]:
        pop = []
        for _ in range(self.population_size):
            ind = DynamicIndicator()
            ind.set_parameter("source_code", self.code_gen.generate_code())
            pop.append(ind)
        return pop

    def _evaluate_population(self, population: list[BaseIndicator], data: pd.DataFrame, targets: dict[str, float]) -> list[float]:
        scores = []
        for ind in population:
            try:
                signals = ind.generate_signals(data)
                metrics = self.metrics_calc.calculate_all(data, signals)
                
                # Multi-objective fitness score
                score = 0.0
                
                # 1. Performance (Profit Factor, Sharpe)
                pf = metrics.get("profit_factor", 0)
                sharpe = metrics.get("sharpe_ratio", 0)
                
                # Weighted contribution
                score += pf * 0.3
                score += sharpe * 0.3
                
                # 2. Robustness (Low Drawdown)
                mdd = metrics.get("max_drawdown", 1.0)
                score -= mdd * 0.2
                
                # 3. Efficiency (Win Rate)
                wr = metrics.get("win_rate", 0)
                score += wr * 0.1
                
                # 4. Target Matching (Proximity to user-defined targets)
                # If a metric is provided in targets, penalize deviation
                target_bonus = 0.0
                for target_name, target_val in targets.items():
                    if target_name in metrics:
                        actual = metrics[target_name]
                        # Normalized distance (capped at 1.0)
                        if target_val != 0:
                            dist = abs(actual - target_val) / abs(target_val)
                            target_bonus += max(0, 0.2 * (1.0 - min(1.0, dist)))
                score += target_bonus
                
                # 5. Complexity Penalty (Occam's Razor)
                formula_len = len(ind.get_formula())
                score -= (formula_len / 1000.0) * 0.05 # Reduced penalty for AI evolution
                
                scores.append(max(0.001, score)) # Ensure non-zero
            except Exception as e:
                logger.warning(f"Evaluation failed for indicator: {e}")
                scores.append(0.0)
        return scores

    def _crossover(self, p1: BaseIndicator, p2: BaseIndicator) -> BaseIndicator:
        """Tree-based crossover of indicator formulas."""
        from monte_neo.utils.ast_utils import crossover_trees
        
        f1 = p1.get_formula()
        f2 = p2.get_formula()
        
        try:
            new_formula = crossover_trees(f1, f2)
        except Exception:
            new_formula = f1 # Fallback
            
        child = DynamicIndicator()
        child.set_parameter("source_code", new_formula)
        return child

    def _mutate(self, p: BaseIndicator) -> BaseIndicator:
        """Heuristic-based mutation with symbolic tree manipulation."""
        formula = p.get_formula()
        
        # 1. Subtree Replacement
        if self.rng.random() < 0.5:
            new_part = self.code_gen.generate_code(depth=1)
            # Wrap in a random operation
            op = self.rng.choice(["+", "-", "*", "/"])
            new_formula = f"({formula} {op} {new_part})"
        # 2. Parameter Tweak
        else:
            # Look for integers in the formula and tweak them
            import re
            numbers = re.findall(r'\d+', formula)
            if numbers:
                target = self.rng.choice(numbers)
                try:
                    val = int(target)
                    new_val = max(2, val + self.rng.integers(-5, 6))
                    new_formula = formula.replace(target, str(new_val), 1)
                except Exception:
                    new_formula = formula
            else:
                new_formula = formula
            
        child = DynamicIndicator()
        child.set_parameter("source_code", new_formula)
        return child
