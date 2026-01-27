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

    def evaluate(self, wfo_result: Any, mc_results: List[Dict[str, Any]] = None, 
                 stress_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Evaluates the results of Walk-Forward Optimization, Monte Carlo and Stress Tests.
        
        Args:
            wfo_result: WalkForwardResult object.
            mc_results: Optional list of Monte Carlo simulation results.
            stress_results: Optional dictionary with stress test results.
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

        # Monte Carlo Robustness
        mc_score = 1.0
        if mc_results:
            profitable_mc = sum(1 for r in mc_results if r['metrics']['total_return'] > 0) / len(mc_results)
            mc_score = profitable_mc

        # Stress Test Score
        stress_score = 1.0
        if stress_results:
            # Penalize if breaking point is too low (< 10 bps)
            bp = stress_results.get('breaking_point', {}).get('breaking_point_bps', 100)
            if isinstance(bp, (int, float)) and bp < 15:
                stress_score *= 0.5
            
            # Penalize if sensitivity is high
            sensitivity = stress_results.get('sensitivity', {}).get('std_return_variation', 0)
            if sensitivity > 0.05: # more than 5% variation for 10% param change
                stress_score *= 0.7

            # Black Swan survival
            bs_return = stress_results.get('black_swan', {}).get('total_return', 0)
            if bs_return < -0.3: # Strategy blows up
                stress_score *= 0.3

        # Robustness Score (0-100)
        # 30% WFE, 20% Pass Rate, 20% Consistency, 15% MC, 15% Stress
        score = (wfe * 30.0) + (pass_rate * 20.0) + (consistency * 20.0) + (mc_score * 15.0) + (stress_score * 15.0)
        score = max(0.0, min(100.0, score * 100.0 if score <= 1.0 else score))
        
        is_ready = score >= 75.0 and wfe >= self.min_wfe and pass_rate >= 0.6 and stress_score > 0.5
        
        status = {
            'robustness_score': round(score, 2),
            'wfe': round(wfe, 4),
            'pass_rate': round(pass_rate, 4),
            'consistency': round(consistency, 4),
            'mc_robustness': round(mc_score, 4),
            'stress_test_score': round(stress_score, 4),
            'is_production_ready': is_ready,
            'recommendation': self._get_recommendation(score, wfe, is_ready, stress_score)
        }
        
        return status

    def _get_recommendation(self, score: float, wfe: float, is_ready: bool, stress_score: float = 1.0) -> str:
        if is_ready:
            return "✅ HIGHLY RECOMMENDED for Production. Robust performance and stress-resistant."
        elif stress_score < 0.6:
            return "❌ REJECTED. Strategy is too fragile to market conditions or trading costs."
        elif score > 60:
            return "⚠️ POTENTIALLY ROBUST. Needs more out-of-sample data."
        elif wfe < 0.5:
            return "❌ OVERFITTED. WFE is too low. In-sample performance does not translate to OOS."
        else:
            return "❌ REJECTED. Strategy lacks consistency and robustness."
