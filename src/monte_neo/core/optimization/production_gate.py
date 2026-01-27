import pandas as pd
import numpy as np
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ProductionGate:
    """Evaluates strategy robustness and issues Production Certificates."""
    
    def __init__(self, min_wfe: float = 70.0, min_win_rate: float = 0.5, max_dd: float = 0.25):
        self.min_wfe = min_wfe
        self.min_win_rate = min_win_rate
        self.max_dd = max_dd

    def evaluate(self, wfo_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates the results of Walk-Forward Optimization.
        
        Returns:
            Dictionary with robustness score and production status.
        """
        wfe = wfo_results['wfe']
        avg_is_return = wfo_results['avg_is_return']
        avg_oos_return = wfo_results['avg_oos_return']
        
        # Calculate consistency (variance in OOS returns)
        oos_returns = [f['oos_return'] for f in wfo_results['folds']]
        consistency = 1.0 - (np.std(oos_returns) / (np.abs(np.mean(oos_returns)) + 1e-6))
        consistency = max(0.0, min(1.0, consistency))
        
        # Robustness Score (0-100)
        # Weighted combination of WFE, Consistency, and absolute performance
        score = (wfe * 0.5) + (consistency * 30.0) + (min(1.0, avg_oos_return / 0.1) * 20.0)
        score = max(0.0, min(100.0, score))
        
        is_ready = score >= 80.0 and wfe >= self.min_wfe
        
        status = {
            'robustness_score': score,
            'wfe': wfe,
            'consistency': consistency,
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
