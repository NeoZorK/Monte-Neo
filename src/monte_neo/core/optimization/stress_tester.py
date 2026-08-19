
import logging
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.core.mlx_engine import MLXBacktestEngine
from monte_neo.indicators.base import BaseIndicator, IndicatorConfig

logger = logging.getLogger(__name__)

class StressTester:
    """Advanced stress testing for trading strategies."""
    
    def __init__(self, engine: MLXBacktestEngine | None = None):
        self.engine = engine or MLXBacktestEngine()

    def run_all(self, indicator: BaseIndicator, data: pd.DataFrame) -> dict[str, Any]:
        """Runs all stress tests and returns an overall robustness score."""
        logger.info(f"Running full stress test suite for {indicator.__class__.__name__}")
        
        black_swan = self.black_swan_test(data, indicator)
        sensitivity = self.parameter_sensitivity_analysis(data, indicator)
        breaking_point = self.breaking_point_analysis(data, indicator)
        
        # Calculate a weighted score
        score = 0.0
        # 1. Black Swan Survival (30%)
        if black_swan.get('total_return', 0) > 0:
            score += 30.0
            
        # 2. Parameter Stability (40%)
        # Lower variation is better
        variation = sensitivity.get('std_return_variation', 1.0)
        score += max(0, 40.0 * (1.0 - min(1.0, variation)))
        
        # 3. Cost Tolerance (30%)
        # > 50 bps is good
        bp = breaking_point.get('breaking_point_bps', 0)
        if isinstance(bp, str): # "> 100"
            score += 30.0
        else:
            score += min(30.0, (bp / 50.0) * 30.0)
            
        return {
            "overall_score": score,
            "black_swan": black_swan,
            "sensitivity": sensitivity,
            "breaking_point": breaking_point
        }

    def black_swan_test(self, data: pd.DataFrame, indicator: BaseIndicator,
                        n_events: int = 5, magnitude_std: float = 5.0) -> dict[str, Any]:
        """
        Injects extreme price movements (Black Swans) into the data and checks strategy stability.
        
        Args:
            data: Original OHLCV data.
            indicator: Indicator to test.
            n_events: Number of extreme events to inject.
            magnitude_std: Magnitude of events in standard deviations of returns.
        """
        returns = data['close'].pct_change().dropna()
        std = returns.std()
        
        stressed_data = data.copy()
        event_indices = np.random.choice(data.index[1:], size=n_events, replace=False)
        
        for idx in event_indices:
            direction = np.random.choice([-1, 1])
            shock = 1 + (direction * magnitude_std * std)
            stressed_data.loc[idx:, ['open', 'high', 'low', 'close']] *= shock
            
        results, _ = self.engine.run_full_simulation(stressed_data, indicator, n_scenarios=1)
        return results[0]['metrics'] if results else {}

    def parameter_sensitivity_analysis(self, data: pd.DataFrame, indicator: BaseIndicator,
                                      perturbation: float = 0.1, n_steps: int = 5) -> dict[str, Any]:
        """
        Tests how sensitive the strategy is to small changes in its parameters.
        Creates a 2D sensitivity grid if at least two parameters are found.
        """
        base_params = indicator.get_parameters()
        import re
        source = base_params.get("source_code", "")
        numbers = re.findall(r"(\d+\.?\d*)", source)
        
        if not numbers:
            return {"status": "no_numeric_params_found"}
            
        # 1. Simple 1D Sensitivity (existing logic)
        variations = []
        for i, num_str in enumerate(numbers):
            val = float(num_str)
            for p in np.linspace(-perturbation, perturbation, n_steps):
                if p == 0: continue
                new_val = val * (1 + p)
                if val.is_integer():
                    new_val = round(new_val)
                
                # Replace ONLY the i-th occurrence
                parts = re.split(f"({re.escape(num_str)})", source)
                count = 0
                new_parts = []
                for part in parts:
                    if part == num_str:
                        if count == i:
                            new_parts.append(str(new_val))
                        else:
                            new_parts.append(part)
                        count += 1
                    else:
                        new_parts.append(part)
                new_source = "".join(new_parts)
                
                from monte_neo.indicators.dynamic import DynamicIndicator
                config = IndicatorConfig(name="Sens_Test", parameters={"source_code": new_source})
                temp_indicator = DynamicIndicator(config)
                
                res, _ = self.engine.run_full_simulation(data, temp_indicator, n_scenarios=1)
                if res:
                    variations.append(res[0]['metrics']['total_return'])
        
        # 2. 2D Sensitivity Grid (if we have at least 2 numbers)
        grid_data = None
        if len(numbers) >= 2:
            p1_str, p2_str = numbers[0], numbers[1]
            p1_val, p2_val = float(p1_str), float(p2_str)
            
            p1_range = np.linspace(p1_val * (1-perturbation), p1_val * (1+perturbation), n_steps)
            p2_range = np.linspace(p2_val * (1-perturbation), p2_val * (1+perturbation), n_steps)
            
            grid = np.zeros((n_steps, n_steps))
            for i, v1 in enumerate(p1_range):
                for j, v2 in enumerate(p2_range):
                    # Replace p1 and p2 in source
                    # This is a bit simplified, assumes p1 and p2 are unique enough
                    ns = source.replace(p1_str, str(round(v1) if p1_val.is_integer() else v1), 1)
                    ns = ns.replace(p2_str, str(round(v2) if p2_val.is_integer() else v2), 1)
                    
                    from monte_neo.indicators.dynamic import DynamicIndicator
                    temp_ind = DynamicIndicator(IndicatorConfig(name="Grid", parameters={"source_code": ns}))
                    r, _ = self.engine.run_full_simulation(data, temp_ind, n_scenarios=1)
                    if r:
                        grid[i, j] = r[0]['metrics']['total_return']
            
            grid_data = {
                "p1_name": f"Param1 ({p1_str})",
                "p2_name": f"Param2 ({p2_str})",
                "p1_values": p1_range.tolist(),
                "p2_values": p2_range.tolist(),
                "matrix": grid.tolist()
            }

        return {
            "mean_return_variation": float(np.mean(variations)) if variations else 0,
            "std_return_variation": float(np.std(variations)) if variations else 0,
            "max_drawdown_impact": float(np.max(variations) - np.min(variations)) if variations else 0,
            "grid": grid_data
        }

    def breaking_point_analysis(self, data: pd.DataFrame, indicator: BaseIndicator,
                               max_comm: float = 100.0, step: float = 5.0) -> dict[str, Any]:
        """
        Finds the level of commission/slippage where the strategy stops being profitable.
        """
        current_cost = 0.0
        while current_cost <= max_comm:
            res, _ = self.engine.run_full_simulation(
                data, indicator, n_scenarios=1,
                commission_bps=current_cost, slippage_bps=current_cost
            )
            
            if not res or res[0]['metrics']['total_return'] <= 0:
                return {
                    "breaking_point_bps": current_cost,
                    "max_safe_cost_bps": max(0, current_cost - step)
                }
            
            current_cost += step
            
        return {"breaking_point_bps": "> " + str(max_comm)}
