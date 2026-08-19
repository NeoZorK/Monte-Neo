"""AI-Driven Evolutionary Engine.

Advanced evolutionary optimization with symbolic regression and heuristic-based mutation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from monte_neo.core.gpu_scenarios import normalize_signal_array
from monte_neo.core.mlx_engine import MLXBacktestEngine
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
        metrics_calc: MetricsCalculator | None = None,
        initial_capital: float = 100000.0,
        leverage: float = 1.0,
        progress_callback: Callable[[int, int, str], None] | None = None,
        use_gpu: bool = True
    ):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.metrics_calc = metrics_calc or MetricsCalculator(initial_capital=initial_capital, leverage=leverage)
        self.rng = np.random.default_rng()
        self.code_gen = CodeGenerator(self.rng)
        self.progress_callback = progress_callback
        self.use_gpu = use_gpu
        self.mlx_engine = MLXBacktestEngine(initial_capital=initial_capital, leverage=leverage)
        self.best_individual: BaseIndicator | None = None
        self.history: list[EvolutionStats] = []
        
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
        current_best_fitness = -float('inf')
        stagnation_counter = 0
        
        try:
            for gen in range(generations):
                fitness_scores = self._evaluate_population(population, data, target_metrics, gen)
                
                # Sort by fitness
                combined = sorted(zip(population, fitness_scores), key=lambda x: x[1], reverse=True)
                population = [p for p, f in combined]
                best_fitness = combined[0][1]
                
                if best_overall is None or best_fitness > current_best_fitness + 0.0001:
                    best_overall = population[0]
                    current_best_fitness = best_fitness
                    stagnation_counter = 0
                else:
                    stagnation_counter += 1
                
                logger.info(f"Gen {gen}: Best Fitness = {best_fitness:.4f}")
                
                # Selection & Breeding
                new_population = population[:int(self.population_size * 0.1)] # Elitism 10%
                
                # If stagnant, inject fresh blood
                if stagnation_counter > 3:
                    logger.info(f"Stagnation detected ({stagnation_counter} gens). Injecting fresh blood...")
                    for _ in range(int(self.population_size * 0.3)):
                        ind = DynamicIndicator()
                        ind.set_parameter("source_code", self.code_gen.generate_code())
                        new_population.append(ind)
                    stagnation_counter = 0
                
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

    def _evaluate_population(self, population: list[BaseIndicator], data: pd.DataFrame, targets: dict[str, float], gen: int = 0) -> list[float]:
        """Evaluates the entire population using 3D GPU acceleration (Pop x Scenarios)."""
        if not self.use_gpu:
            # Skip GPU and go straight to fallback if GPU is disabled
            return self._fallback_evaluate(population, data, targets)
            
        try:
            # Используем 3D-бэктест (10 сценариев Monte-Carlo для КАЖДОГО члена популяции прямо в процессе)
            # Это дает на порядок более устойчивые стратегии
            n_scenarios = 5 # Умеренное кол-во для эволюции
            
            results_3d = self.mlx_engine.backtest_population_multi_scenario(
                data=data,
                population=population,
                n_scenarios=n_scenarios,
                use_sl_tp=True,
                return_raw=True
            )
            
            # results_3d: [Population x Scenarios x 6]
            # Layout: 0:ret, 1:trades, 2:winrate, 3:maxdd, 4:pf, 5:sharpe
            scores = []
            for i in range(len(population)):
                # Метрики по всем сценариям для данной особи
                scen_metrics = results_3d[i] # [Scenarios x 6]
                
                # Средние метрики
                avg_pf = np.mean(scen_metrics[:, 4])
                avg_mdd = np.mean(scen_metrics[:, 3])
                avg_trades = np.mean(scen_metrics[:, 1])
                avg_ret = np.mean(scen_metrics[:, 0])
                
                # Fitness score (используем консервативный подход)
                pf = avg_pf
                if np.isnan(pf) or np.isinf(pf) or pf > 100.0: pf = 0.0
                
                # Повышаем значимость прибыли и фактора прибыли
                score = pf * 1.5
                score += (avg_ret * 10.0) # 10% прибыли = +1.0 к скору
                score -= avg_mdd * 2.0   # Штраф за просадку
                
                # Штраф за малое кол-во сделок (минимум 15 для стабильности)
                if avg_trades < 15:
                    score *= (avg_trades / 15.0)
                
                # Бонус за активность (чтобы избежать flat landscape 0.001)
                # Даем крошечный бонус за каждую сделку, даже если стратегия пока убыточна
                if avg_trades > 0:
                    score += min(0.1, avg_trades * 0.001)
                
                # Логируем если нашли что-то интересное или для отладки первых поколений
                if score > 1.0 or (gen == 0 and i < 5):
                    logger.debug(f"Candidate {i}: score={score:.4f}, pf={pf:.2f}, trades={avg_trades:.1f}, ret={avg_ret:.4f}, mdd={avg_mdd:.4f}")
                
                scores.append(max(0.001, score))
            
            return scores

        except Exception as e:
            logger.error(f"3D GPU evaluation failed, falling back to 2D Batch: {e}")
            return self._fallback_evaluate(population, data, targets)

    def _fallback_evaluate(self, population: list[BaseIndicator], data: pd.DataFrame, targets: dict[str, float]) -> list[float]:
        """Fallback to the previous 2D batch method if 3D fails or is disabled."""
        scores = []
        try:
            # 1. Generate all signals first
            raw_signals = [ind.generate_signals_fast(data) for ind in population]
            
            # 2. Prepare signal matrix
            n_pop = len(population)
            n_data = len(data)
            signal_matrix = np.zeros((n_pop, n_data), dtype=np.int32)
            
            for i, sig in enumerate(raw_signals):
                signal_matrix[i] = normalize_signal_array(sig, n_data).astype(np.int32)
                
            # 3. Perform 2D batch
            batch_results = self.metrics_calc.calculate_batch_fast(
                data["close"].values,
                data["high"].values,
                data["low"].values,
                signal_matrix,
                use_sl_tp=True
            )
            
            for i in range(n_pop):
                # Use the same improved fitness logic as in 3D
                pf = batch_results[i, 2] # Profit Factor
                avg_ret = batch_results[i, 0] # Returns
                avg_mdd = batch_results[i, 1] # Drawdown
                avg_trades = batch_results[i, 3] # Trades (index might differ from 3D results, check calculate_batch_fast)
                
                if np.isnan(pf) or np.isinf(pf) or pf > 100.0: pf = 0.0
                
                score = pf * 1.5
                score += (avg_ret * 10.0)
                score -= avg_mdd * 2.0
                
                # Penalty for low trades
                if avg_trades < 15:
                    score *= (avg_trades / 15.0)
                    
                scores.append(max(0.001, score))
            
            return scores
        except Exception as e2:
            logger.error(f"Fallback evaluation also failed: {e2}")
            return [0.001] * len(population)

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
