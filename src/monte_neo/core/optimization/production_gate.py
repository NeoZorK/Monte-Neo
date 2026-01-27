import pandas as pd
import numpy as np
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ProductionGate:
    """Evaluates strategy robustness and issues Production Certificates."""
    
    def __init__(self, min_wfe: float = 0.6, min_win_rate: float = 0.45, max_dd: float = 0.20):
        self.min_wfe = min_wfe
        self.min_win_rate = min_win_rate
        self.max_dd = max_dd

    def evaluate(self, wfo_result: Any, mc_results: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluates the results of Walk-Forward Optimization and Monte Carlo simulations.
        
        Args:
            wfo_result: WalkForwardResult object.
            mc_results: Optional list of Monte Carlo simulation results.
        
        Returns:
            Dictionary with robustness score and production status.
        """
        wfe = getattr(wfo_result, 'efficiency_ratio', 0.0)
        pass_rate = getattr(wfo_result, 'pass_rate', 0.0)
        
        # Calculate consistency from windows
        test_returns = []
        if hasattr(wfo_result, 'windows'):
            for w in wfo_result.windows:
                if 'total_return' in w.test_metrics:
                    test_returns.append(w.test_metrics['total_return'])
        
        consistency = 0.0
        if test_returns:
            mean_ret = np.mean(test_returns)
            if abs(mean_ret) > 1e-6:
                consistency = 1.0 - (np.std(test_returns) / abs(mean_ret))
        
        consistency = max(0.0, min(1.0, consistency))
        
        # Monte Carlo Robustness (if available)
        mc_score = 1.0
        if mc_results:
            # Check what percentage of MC scenarios are profitable
            profitable_mc = sum(1 for r in mc_results if r['metrics']['total_return'] > 0) / len(mc_results)
            mc_score = profitable_mc

        # Robustness Score (0-100)
        # 40% WFE, 20% Pass Rate, 20% Consistency, 20% MC
        score = (wfe * 40.0) + (pass_rate * 20.0) + (consistency * 20.0) + (mc_score * 20.0)
        score = max(0.0, min(100.0, score * 100.0 if score <= 1.0 else score))
        
        is_ready = score >= 75.0 and wfe >= self.min_wfe and pass_rate >= 0.6
        
        status = {
            'robustness_score': round(score, 2),
            'wfe': round(wfe, 4),
            'pass_rate': round(pass_rate, 4),
            'consistency': round(consistency, 4),
            'mc_robustness': round(mc_score, 4),
            'is_production_ready': is_ready,
            'recommendation': self._get_recommendation(score, wfe, is_ready)
        }
        
        return status

    def _get_recommendation(self, score: float, wfe: float, is_ready: bool) -> str:
        if is_ready:
            return "✅ HIGHLY RECOMMENDED for Production. Robust performance across all folds."
        elif score > 60:
            return "⚠️ POTENTIALLY ROBUST. Needs more stress testing (Monte Carlo)."
        elif wfe < 50:
            return "❌ OVERFITTED. WFE is too low. In-sample performance does not translate to OOS."
        else:
            return "❌ REJECTED. Strategy lacks consistency and robustness."
