"""Sensitivity analysis module.

Tests indicator stability across parameter variations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator
    from monte_neo.metrics.calculator import MetricsCalculator

logger = get_logger(__name__)


@dataclass
class SensitivityResult:
    """Sensitivity analysis result."""

    parameter_name: str
    base_value: float
    variations: list[float] = field(default_factory=list)
    metrics_by_variation: dict = field(default_factory=dict)
    stability_score: float = 0.0
    is_stable: bool = False


class SensitivityAnalyzer:
    """Sensitivity analysis for parameter robustness."""

    def __init__(
        self,
        variation_range: float = 0.10,
        n_steps: int = 5,
    ) -> None:
        """Initialize sensitivity analyzer.

        Args:
            variation_range: Variation range (e.g., 0.10 for ±10%).
            n_steps: Number of steps in each direction.
        """
        self.variation_range = variation_range
        self.n_steps = n_steps

    def analyze_parameter(
        self,
        indicator: BaseIndicator,
        param_name: str,
        base_value: float,
        data: pd.DataFrame,
        metrics_calc: MetricsCalculator,
    ) -> SensitivityResult:
        """Analyze sensitivity to a single parameter.

        Args:
            indicator: Indicator to test.
            param_name: Parameter name to vary.
            base_value: Base parameter value.
            data: OHLCV data.
            metrics_calc: Metrics calculator.

        Returns:
            SensitivityResult with analysis.
        """
        # Generate variations
        variations = self._generate_variations(base_value)
        metrics_by_variation = {}

        for value in variations:
            # Update indicator parameter
            indicator.set_parameter(param_name, value)

            # Generate signals and calculate metrics
            signals = indicator.generate_signals(data)
            metrics = metrics_calc.calculate_all(data, signals)
            metrics_by_variation[value] = metrics

        # Reset to base value
        indicator.set_parameter(param_name, base_value)

        # Calculate stability score
        stability_score = self._calculate_stability(metrics_by_variation)
        is_stable = stability_score >= 0.7  # 70% stability threshold

        result = SensitivityResult(
            parameter_name=param_name,
            base_value=base_value,
            variations=variations,
            metrics_by_variation=metrics_by_variation,
            stability_score=stability_score,
            is_stable=is_stable,
        )

        logger.info(f"Sensitivity {param_name}: stability={stability_score:.2f}")
        return result

    def analyze_all_parameters(
        self,
        indicator: BaseIndicator,
        data: pd.DataFrame,
        metrics_calc: MetricsCalculator,
    ) -> list[SensitivityResult]:
        """Analyze sensitivity to all indicator parameters.

        Args:
            indicator: Indicator to test.
            data: OHLCV data.
            metrics_calc: Metrics calculator.

        Returns:
            List of SensitivityResults.
        """
        results = []

        for param_name, param_value in indicator.get_parameters().items():
            if isinstance(param_value, (int, float)):
                result = self.analyze_parameter(
                    indicator, param_name, float(param_value), data, metrics_calc
                )
                results.append(result)

        return results

    def get_stability_report(
        self,
        results: list[SensitivityResult],
    ) -> dict:
        """Generate stability report from results.

        Args:
            results: List of sensitivity results.

        Returns:
            Report dictionary.
        """
        total_params = len(results)
        stable_params = sum(1 for r in results if r.is_stable)
        avg_stability = np.mean([r.stability_score for r in results]) if results else 0

        return {
            "total_parameters": total_params,
            "stable_parameters": stable_params,
            "unstable_parameters": total_params - stable_params,
            "average_stability": float(avg_stability),
            "overall_stable": stable_params == total_params,
            "parameter_details": {
                r.parameter_name: {
                    "base_value": r.base_value,
                    "stability_score": r.stability_score,
                    "is_stable": r.is_stable,
                }
                for r in results
            },
        }

    def _generate_variations(self, base_value: float) -> list[float]:
        """Generate parameter variations.

        Args:
            base_value: Base parameter value.

        Returns:
            List of variation values.
        """
        variations = [base_value]  # Include base

        for i in range(1, self.n_steps + 1):
            factor = i * self.variation_range / self.n_steps
            variations.append(base_value * (1 - factor))  # Lower
            variations.append(base_value * (1 + factor))  # Higher

        return sorted(set(variations))

    def _calculate_stability(
        self,
        metrics_by_variation: dict[float, dict],
    ) -> float:
        """Calculate stability score across variations.

        Args:
            metrics_by_variation: Metrics for each parameter value.

        Returns:
            Stability score 0-1.
        """
        if len(metrics_by_variation) < 2:
            return 1.0

        # Key metrics for stability assessment
        key_metrics = ["profit_factor", "sharpe_ratio", "max_drawdown"]

        stability_scores = []

        for metric in key_metrics:
            values = []
            for variation_metrics in metrics_by_variation.values():
                if metric in variation_metrics:
                    values.append(variation_metrics[metric])

            if len(values) >= 2:
                # Coefficient of variation (lower = more stable)
                mean_val = np.mean(values)
                if mean_val != 0:
                    cv = np.std(values) / abs(mean_val)
                    # Convert to stability score (1 = stable, 0 = unstable)
                    stability = max(0, 1 - cv)
                    stability_scores.append(stability)

        return float(np.mean(stability_scores)) if stability_scores else 1.0
