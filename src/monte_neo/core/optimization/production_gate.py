"""Production Gate Module.

Final validation and certification before deployment.
"""

from __future__ import annotations

import os
from typing import Dict, Any, Optional

from monte_neo.indicators.base import BaseIndicator
from monte_neo.core.optimization.certification import RobustnessCertifier
from monte_neo.core.optimization.production_exporter import ProductionExporter
from monte_neo.core.optimization.stress_tester import StressTester
from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)

class ProductionGate:
    """The final checkpoint for indicators before they go live."""

    def __init__(self, export_dir: str = "exports"):
        self.certifier = RobustnessCertifier(os.path.join(export_dir, "certificates"))
        self.exporter = ProductionExporter(os.path.join(export_dir, "production"))
        self.stress_tester = StressTester()

    def process(self, indicator: BaseIndicator, data: Dict[str, Any], validation_results: Dict[str, Any]) -> Dict[str, Any]:
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
