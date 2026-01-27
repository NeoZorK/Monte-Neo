import numpy as np
import pandas as pd
from typing import List, Dict, Any
import logging
from ..acceleration.cpp_metal import metal_engine

logger = logging.getLogger(__name__)

class GPUOptimizer:
    """Orchestrates GPU-accelerated Grid Search and Backtesting using Metal."""
    
    def __init__(self, driver: str = "cpp"):
        # Map string driver to MetalBridge enum
        driver_map = {
            "cpp": metal_engine.Driver.CPP,
            "objc": metal_engine.Driver.OBJC,
            "swift": metal_engine.Driver.SWIFT
        }
        selected_driver = driver_map.get(driver.lower(), metal_engine.Driver.CPP)
        
        self.bridge = metal_engine.MetalBacktestBridge(selected_driver)
        if not self.bridge.init():
            raise RuntimeError(f"Failed to initialize Metal GPU Bridge with driver: {driver}")
        logger.info(f"GPUOptimizer: Metal Bridge initialized successfully with driver: {driver}")

    def run_grid_search(self, df: pd.DataFrame, param_grid: Dict[str, List[float]]) -> pd.DataFrame:
        """
        Runs a grid search across all parameter combinations on the GPU.
        
        Args:
            df: DataFrame with OHLCV data
            param_grid: Dictionary of parameter ranges (e.g., {'rsi_p': [10, 14, 20]})
            
        Returns:
            DataFrame with results for each combination
        """
        # 1. Prepare data
        candles = [
            metal_engine.Candle(
                float(row.open), float(row.high), float(row.low), float(row.close), float(row.volume)
            ) for row in df.itertuples()
        ]
        
        # 2. Generate parameter combinations
        import itertools
        keys = list(param_grid.keys())
        combinations = list(itertools.product(*[param_grid[k] for k in keys]))
        n_scenarios = len(combinations)
        
        # Flatten combinations for Metal (assuming 5 params per scenario as per shader)
        # Order: RSI_P, ATR_P, SL_MULT, TP_MULT, TS_MULT
        flat_params = []
        for combo in combinations:
            # Map combo to the 5 params expected by shader
            # If combo has fewer, pad with 0
            p = list(combo) + [0.0] * (5 - len(combo))
            flat_params.extend(p[:5])
            
        logger.info(f"GPUOptimizer: Starting grid search for {n_scenarios} scenarios...")
        
        import time
        start_t = time.perf_counter()
        
        # 3. Run on GPU
        results = self.bridge.run_backtest(candles, flat_params, n_scenarios)
        
        duration = time.perf_counter() - start_t
        logger.info(f"GPUOptimizer: Metal Grid Search completed in {duration:.4f} seconds ({n_scenarios / (duration + 1e-9):.2f} scenarios/sec)")
        
        # 4. Process results
        processed_results = []
        for i, res in enumerate(results):
            entry = {keys[j]: combinations[i][j] for j in range(len(keys))}
            entry.update({
                'total_return': res.total_return,
                'trade_count': res.trade_count,
                'win_rate': res.win_rate,
                'max_drawdown': res.max_drawdown
            })
            processed_results.append(entry)
            
        return pd.DataFrame(processed_results)

    def run_walk_forward(self, df: pd.DataFrame, param_grid: Dict[str, List[float]], 
                         train_size: float = 0.7, n_folds: int = 5) -> Dict[str, Any]:
        """
        Runs Walk-Forward Optimization on the GPU.
        
        Args:
            df: DataFrame with OHLCV data
            param_grid: Dictionary of parameter ranges
            train_size: Ratio of training data in each fold
            n_folds: Number of walk-forward folds
            
        Returns:
            Dictionary with WFO results and Walk-Forward Efficiency (WFE)
        """
        n_bars = len(df)
        fold_size = n_bars // n_folds
        
        fold_results = []
        oos_returns = []
        is_returns = []
        
        logger.info(f"GPUOptimizer: Starting Walk-Forward Optimization with {n_folds} folds...")
        
        for i in range(n_folds):
            # Calculate indices for this fold
            start_idx = i * fold_size
            end_idx = (i + 1) * fold_size
            
            fold_df = df.iloc[start_idx:end_idx]
            split_point = int(len(fold_df) * train_size)
            
            train_df = fold_df.iloc[:split_point]
            test_df = fold_df.iloc[split_point:]
            
            # 1. In-Sample (IS) Optimization
            is_results = self.run_grid_search(train_df, param_grid)
            best_scenario = is_results.sort_values('total_return', ascending=False).iloc[0]
            
            # 2. Out-of-Sample (OOS) Validation
            # Create a single-scenario param grid with best IS params
            best_params = {k: [best_scenario[k]] for k in param_grid.keys()}
            oos_result = self.run_grid_search(test_df, best_params).iloc[0]
            
            fold_results.append({
                'fold': i,
                'best_params': {k: best_scenario[k] for k in param_grid.keys()},
                'is_return': best_scenario['total_return'],
                'oos_return': oos_result['total_return'],
                'is_trades': best_scenario['trade_count'],
                'oos_trades': oos_result['trade_count']
            })
            
            is_returns.append(best_scenario['total_return'])
            oos_returns.append(oos_result['total_return'])
            
        # Calculate WFE (Walk-Forward Efficiency)
        avg_is = np.mean(is_returns) if is_returns else 0
        avg_oos = np.mean(oos_returns) if oos_returns else 0
        wfe = (avg_oos / avg_is) * 100 if avg_is != 0 else 0
        
        return {
            'wfe': wfe,
            'folds': fold_results,
            'avg_is_return': avg_is,
            'avg_oos_return': avg_oos
        }
