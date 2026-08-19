"""Production Gate Module.

Final validation and certification before deployment.
"""

from __future__ import annotations

import os
from typing import Any

from monte_neo.core.optimization.certification import RobustnessCertifier
from monte_neo.core.optimization.production_exporter import ProductionExporter
from monte_neo.core.optimization.stress_tester import StressTester
from monte_neo.indicators.base import BaseIndicator
from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)

class ProductionGate:
    """The final checkpoint for indicators before they go live."""

    def __init__(self, export_dir: str = "exports", min_wfe: float = 0.5):
        self.certifier = RobustnessCertifier(os.path.join(export_dir, "certificates"))
        self.exporter = ProductionExporter(os.path.join(export_dir, "production"))
        self.stress_tester = StressTester()
        self.min_wfe = min_wfe

    def evaluate(self, wfo_result: Any, mc_results: list[dict[str, Any]], stress_results: dict[str, Any]) -> dict[str, Any]:
        """Evaluates robustness based on WFA, MC, and stress tests."""
        # 1. WFA Efficiency Score (0-40 points)
        wfe_score = min(40, (wfo_result.efficiency_ratio / self.min_wfe) * 20)
        
        # 2. MC Stability Score (0-30 points)
        # Based on how many MC runs were profitable
        profitable_runs = sum(1 for r in mc_results if r.get('total_return', 0) > 0)
        mc_pass_rate = profitable_runs / len(mc_results) if mc_results else 0
        mc_score = mc_pass_rate * 30
        
        # 3. Stress Test Score (0-30 points)
        # Simplified scoring for stress tests
        stress_score = 30 if stress_results.get('breaking_point', {}).get('breaking_point_bps', 0) > 50 else 15
        
        robustness_score = wfe_score + mc_score + stress_score
        is_ready = robustness_score >= 70
        
        recommendation = "Ready for Production" if is_ready else "Requires Further Optimization"
        if robustness_score < 50:
            recommendation = "Reject: Unstable Strategy"
            
        return {
            "robustness_score": int(robustness_score),
            "is_production_ready": is_ready,
            "recommendation": recommendation,
            "wfe_score": wfe_score,
            "mc_score": mc_score,
            "stress_score": stress_score
        }

    def process(self, indicator: BaseIndicator, data: dict[str, Any], validation_results: dict[str, Any]) -> dict[str, Any]:
        """
        Runs final stress tests, generates a certificate, and exports if passed.
        """
        logger.info(f"Processing production gate for {indicator.__class__.__name__}")

        # 1. Final Stress Test
        stress_results = self.stress_tester.run_all(indicator, data)
        validation_results["stress_test_score"] = stress_results.get("overall_score", 0.0)

        # 2. Decision Logic
        is_ready = (
            validation_results.get("robustness_score", 0.0) > 70.0 and
            validation_results.get("stress_test_score", 0.0) > 60.0 and
            validation_results.get("is_production_ready", False)
        )

        # 3. Generate Certificate
        cert_path = self.certifier.generate_certificate(indicator.__class__.__name__, validation_results)
        
        # 4. Export if ready
        export_path = None
        if is_ready:
            export_path = self.exporter.export(indicator, validation_results)
            logger.info(f"Indicator certified and exported to {export_path}")
        else:
            logger.warning("Indicator failed production gate requirements.")

        return {
            "is_certified": is_ready,
            "certificate_path": cert_path,
            "export_path": export_path,
            "final_score": (validation_results.get("robustness_score", 0.0) + validation_results.get("stress_test_score", 0.0)) / 2
        }
