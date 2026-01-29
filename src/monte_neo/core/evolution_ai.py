"""AI-Driven Evolutionary Engine.

Advanced evolutionary optimization with symbolic regression and heuristic-based mutation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from monte_neo.indicators.base import BaseIndicator
from monte_neo.indicators.code_gen import CodeGenerator
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.utils.logger import get_logger
from monte_neo.core.gpu_scenarios import normalize_signal_array

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
        metrics_calc: MetricsCalculator | None = None,
        initial_capital: float = 100000.0,
        leverage: float = 1.0,
        progress_callback: Callable[[int, int, str], None] | None = None
    ):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.metrics_calc = metrics_calc or MetricsCalculator(initial_capital=initial_capital, leverage=leverage)
        self.rng = np.random.default_rng()
        self.code_gen = CodeGenerator(self.rng)
        self.progress_callback = progress_callback
        
        # Heuristics: Map weaknesses to potential fixes
        self.heuristics = {
            "high_drawdown": ["trend_filter", "volatility_exit"],
            "low_winrate": ["mean_reversion_filter", "tighter_sl"],
            "instability": ["smoothing", "higher_timeframe_confirmation"]
        }

    def evolve(self, data: pd.DataFrame, target_metrics: dict[str, float], generations: int = 10) -> BaseIndicator:
        """Runs the AI-driven evolution process."""
        population = self._initialize_population()
        best_overall = None
        
        try:
            for gen in range(generations):
                fitness_scores = self._evaluate_population(population, data, target_metrics)
                
                # Sort by fitness
                combined = sorted(zip(population, fitness_scores), key=lambda x: x[1], reverse=True)
                population = [p for p, f in combined]
                best_fitness = combined[0][1]
                
                if best_overall is None or best_fitness > self._get_fitness(best_overall, data, target_metrics):
                    best_overall = population[0]
                
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

                if self.progress_callback:
                    self.progress_callback(gen + 1, generations, f"AI Evolution Gen {gen + 1}: Best Fitness {best_fitness:.4f}")
        
        except KeyboardInterrupt:
            logger.info("Evolution interrupted by user. Returning best found so far.")
            if best_overall is None and population:
                best_overall = population[0]
        
        return best_overall if best_overall else population[0]

    def _get_fitness(self, indicator: BaseIndicator, data: pd.DataFrame, targets: dict[str, float]) -> float:
        """Helper to get fitness of a single indicator."""
        try:
            signals = indicator.generate_signals_fast(data)
            metrics = self.metrics_calc.calculate_all(data, signals)
            return self._calculate_fitness(metrics, targets)
        except Exception:
            return 0.0

    def _initialize_population(self) -> list[BaseIndicator]:
        pop: list[BaseIndicator] = []
        for _ in range(self.population_size):
            ind = DynamicIndicator()
            ind.set_parameter("source_code", self.code_gen.generate_code())
            pop.append(ind)
        return pop

    def _evaluate_population(self, population: list[BaseIndicator], data: pd.DataFrame, targets: dict[str, float]) -> list[float]:
        """Evaluates the entire population using vectorized batch calculation."""
        scores = []
        try:
            # 1. Generate all signals first (can be parallelized further if needed)
            raw_signals = [ind.generate_signals_fast(data) for ind in population]
            
            # 2. Prepare signal matrix for batch calculation
            n_pop = len(population)
            n_data = len(data)
            signal_matrix = np.zeros((n_pop, n_data), dtype=np.int32)
            
            for i, sig in enumerate(raw_signals):
                signal_matrix[i] = normalize_signal_array(sig, n_data).astype(np.int32)
                
            # 3. Perform high-performance batch metrics calculation
            # This uses Numba/Vectorized logic internally
            batch_results = self.metrics_calc.calculate_batch_fast(
                data["close"].values,
                data["high"].values,
                data["low"].values,
                signal_matrix,
                use_sl_tp=True, # Always use SL/TP for evolution to find realistic strategies
                sl_pct=0.02,    # Default 2% SL
                tp_pct=0.04     # Default 4% TP
            )
            
            # batch_results shape is (n_pop, 4) -> [return, drawdown, profit_factor, trade_count]
            for i in range(n_pop):
                metrics = {
                    "total_return": batch_results[i, 0],
                    "max_drawdown": batch_results[i, 1],
                    "profit_factor": batch_results[i, 2],
                    "trade_count": batch_results[i, 3]
                }
                
                # Multi-objective fitness score
                score = 0.0
                
                # 1. Performance (Profit Factor)
                pf = metrics["profit_factor"]
                if np.isinf(pf) or pf > 100.0:
                    pf = 100.0
                score += pf * 0.4 # Increased weight for PF
                
                # 2. Robustness (Low Drawdown)
                mdd = metrics["max_drawdown"]
                score -= mdd * 0.3 # Increased penalty for DD
                
                # 3. Trade count sanity check
                trades = metrics["trade_count"]
                if trades < 10:
                    score *= 0.1 # Severe penalty for too few trades
                elif trades > 100:
                    score *= 0.8 # Slight penalty for over-trading
                
                # 4. Target Matching
                target_bonus = 0.0
                for target_name, target_val in targets.items():
                    if target_name in metrics:
                        actual = metrics[target_name]
                        if target_val != 0:
                            dist = abs(actual - target_val) / abs(target_val)
                            target_bonus += max(0, 0.2 * (1.0 - min(1.0, dist)))
                score += target_bonus
                
                # 5. Complexity Penalty
                formula_len = len(population[i].get_formula())
                score -= (formula_len / 1000.0) * 0.05
                
                scores.append(max(0.001, score))
                
        except Exception as e:
            logger.error(f"Batch evaluation failed: {e}")
            # Fallback to individual evaluation if batch fails
            scores = []
            for ind in population:
                try:
                    signals = ind.generate_signals(data)
                    metrics = self.metrics_calc.calculate_all(data, signals)
                    # Simple fallback score
                    pf = metrics.get("profit_factor", 0)
                    scores.append(pf if not np.isinf(pf) else 10.0)
                except Exception:
                    scores.append(0.0)
                    
        return scores

    def _crossover(self, p1: BaseIndicator, p2: BaseIndicator) -> BaseIndicator:
        """Tree-based crossover of indicator formulas."""
        from monte_neo.utils.ast_utils import crossover_trees
        
        # Use raw source code for dynamic indicators to avoid "Dynamic: " prefix breaking AST
        f1 = p1.source_code if hasattr(p1, "source_code") else p1.get_formula()
        f2 = p2.source_code if hasattr(p2, "source_code") else p2.get_formula()
        
        try:
            new_formula = crossover_trees(f1, f2)
        except Exception:
            new_formula = f1 # Fallback
            
        child = DynamicIndicator()
        child.set_parameter("source_code", new_formula)
        return child

    def _mutate(self, p: BaseIndicator) -> BaseIndicator:
        """Heuristic-based mutation with symbolic tree manipulation."""
        # Use raw source code for dynamic indicators to avoid "Dynamic: " prefix breaking AST
        formula = p.source_code if hasattr(p, "source_code") else p.get_formula()
        
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
