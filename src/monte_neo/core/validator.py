"""Overfitting validator module.

Validates indicators to prevent overfitting.
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
class ValidationResult:
    """Validation result."""
    
    passed: bool
    overall_score: float
    in_sample_metrics: dict = field(default_factory=dict)
    out_sample_metrics: dict = field(default_factory=dict)
    cross_val_scores: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class OverfitValidator:
    """Validate indicators for overfitting."""

    def __init__(
        self,
        min_trades: int = 30,
        min_oos_ratio: float = 0.6,
        n_folds: int = 5,
    ) -> None:
        """Initialize validator.

        Args:
            min_trades: Minimum trades required.
            min_oos_ratio: Minimum OOS/IS performance ratio.
            n_folds: Number of cross-validation folds.
        """
        self.min_trades = min_trades
        self.min_oos_ratio = min_oos_ratio
        self.n_folds = n_folds

    def validate(
        self,
        indicator: BaseIndicator,
        data: pd.DataFrame,
        metrics_calc: MetricsCalculator,
        target_metrics: dict[str, float],
    ) -> ValidationResult:
        """Full validation check.

        Args:
            indicator: Indicator to validate.
            data: Full OHLCV data.
            metrics_calc: Metrics calculator.
            target_metrics: Target metrics.

        Returns:
            ValidationResult with all checks.
        """
        warnings = []
        
        # In-sample / Out-of-sample split
        split_idx = int(len(data) * 0.7)
        in_sample = data.iloc[:split_idx]
        out_sample = data.iloc[split_idx:]

        # In-sample metrics
        is_signals = indicator.generate_signals(in_sample)
        is_metrics = metrics_calc.calculate_all(in_sample, is_signals)

        # Out-of-sample metrics
        oos_signals = indicator.generate_signals(out_sample)
        oos_metrics = metrics_calc.calculate_all(out_sample, oos_signals)

        # Check minimum trades
        if is_metrics.get("trade_count", 0) < self.min_trades:
            warnings.append(f"In-sample trades ({is_metrics.get('trade_count', 0)}) < {self.min_trades}")

        if oos_metrics.get("trade_count", 0) < self.min_trades // 3:
            warnings.append("Insufficient out-of-sample trades")

        # Check OOS/IS ratio
        oos_ratio = self._calculate_oos_ratio(is_metrics, oos_metrics)
        if oos_ratio < self.min_oos_ratio:
            warnings.append(f"OOS/IS ratio ({oos_ratio:.2f}) < {self.min_oos_ratio}")

        # Cross-validation
        cv_scores = self._cross_validate(indicator, data, metrics_calc)
        avg_cv = np.mean(cv_scores) if cv_scores else 0
        cv_std = np.std(cv_scores) if cv_scores else 0

        if cv_std > 0.3:
            warnings.append(f"High CV variance ({cv_std:.2f})")

        # Check target metrics on OOS
        meets_targets = self._check_targets(oos_metrics, target_metrics)
        if not meets_targets:
            warnings.append("OOS metrics don't meet targets")

        # Overall score
        overall_score = self._calculate_overall_score(
            oos_ratio, avg_cv, cv_std, meets_targets
        )

        return ValidationResult(
            passed=len(warnings) == 0 and overall_score >= 0.7,
            overall_score=overall_score,
            in_sample_metrics=is_metrics,
            out_sample_metrics=oos_metrics,
            cross_val_scores=cv_scores,
            warnings=warnings,
        )

    def _calculate_oos_ratio(
        self,
        is_metrics: dict,
        oos_metrics: dict,
    ) -> float:
        """Calculate out-of-sample to in-sample ratio."""
        key_metric = "sharpe_ratio"
        
        is_val = is_metrics.get(key_metric, 0)
        oos_val = oos_metrics.get(key_metric, 0)
        
        if is_val <= 0:
            return 0.0
        
        return oos_val / is_val

    def _cross_validate(
        self,
        indicator: BaseIndicator,
        data: pd.DataFrame,
        metrics_calc: MetricsCalculator,
    ) -> list[float]:
        """Perform k-fold cross-validation."""
        scores = []
        fold_size = len(data) // self.n_folds

        for i in range(self.n_folds):
            # Create test fold
            test_start = i * fold_size
            test_end = (i + 1) * fold_size

            train = pd.concat([data.iloc[:test_start], data.iloc[test_end:]])
            test = data.iloc[test_start:test_end]

            if len(test) < 10:
                continue

            # Test on fold
            signals = indicator.generate_signals(test)
            metrics = metrics_calc.calculate_all(test, signals)
            scores.append(metrics.get("sharpe_ratio", 0))

        return scores

    def _check_targets(
        self,
        metrics: dict,
        targets: dict,
    ) -> bool:
        """Check if metrics meet targets."""
        for name, target in targets.items():
            if name not in metrics:
                continue
            
            actual = metrics[name]
            
            if name in ["max_drawdown", "consecutive_losses"]:
                if actual > target:
                    return False
            else:
                if actual < target:
                    return False
        
        return True

    def _calculate_overall_score(
        self,
        oos_ratio: float,
        cv_mean: float,
        cv_std: float,
        meets_targets: bool,
    ) -> float:
        """Calculate overall validation score."""
        score = 0.0
        
        # OOS ratio contribution (0-0.4)
        score += min(0.4, oos_ratio * 0.4)
        
        # CV mean contribution (0-0.3)
        score += min(0.3, cv_mean * 0.1)
        
        # CV stability contribution (0-0.2)
        stability = max(0, 1 - cv_std)
        score += stability * 0.2
        
        # Meets targets contribution (0.1)
        if meets_targets:
            score += 0.1

        return min(1.0, score)

    def quick_check(
        self,
        indicator: BaseIndicator,
        data: pd.DataFrame,
        metrics_calc: MetricsCalculator,
    ) -> bool:
        """Quick validation check.

        Args:
            indicator: Indicator to check.
            data: OHLCV data.
            metrics_calc: Metrics calculator.

        Returns:
            True if passes quick checks.
        """
        signals = indicator.generate_signals(data)
        metrics = metrics_calc.calculate_all(data, signals)

        # Check minimum trades
        if metrics.get("trade_count", 0) < self.min_trades:
            return False

        # Check profit factor
        if metrics.get("profit_factor", 0) < 1.0:
            return False

        # Check max drawdown
        if metrics.get("max_drawdown", 1) > 0.5:
            return False

        return True
