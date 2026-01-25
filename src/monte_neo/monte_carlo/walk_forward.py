"""Walk-forward analysis module.

Implements rolling walk-forward testing for robust out-of-sample validation.
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
class WalkForwardWindow:
    """Single walk-forward window result."""

    window_idx: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_metrics: dict = field(default_factory=dict)
    test_metrics: dict = field(default_factory=dict)
    passed: bool = False


@dataclass
class WalkForwardResult:
    """Complete walk-forward analysis result."""

    windows: list[WalkForwardWindow] = field(default_factory=list)
    overall_passed: bool = False
    pass_rate: float = 0.0
    avg_test_performance: dict = field(default_factory=dict)
    efficiency_ratio: float = 0.0  # test_performance / train_performance


class WalkForwardAnalyzer:
    """Walk-forward analysis for out-of-sample validation."""

    def __init__(
        self,
        n_splits: int = 5,
        train_pct: float = 0.7,
        anchored: bool = False,
    ) -> None:
        """Initialize walk-forward analyzer.

        Args:
            n_splits: Number of walk-forward windows.
            train_pct: Training data percentage per window.
            anchored: If True, training always starts from beginning.
        """
        self.n_splits = n_splits
        self.train_pct = train_pct
        self.anchored = anchored

    def generate_scenarios(
        self,
        data: pd.DataFrame,
        n_splits: int | None = None,
    ) -> list[pd.DataFrame]:
        """Generate walk-forward test scenarios (out-of-sample segments).

        Args:
            data: OHLCV data.
            n_splits: Number of splits override.

        Returns:
            List of DataFrames representing out-of-sample periods.
        """
        if n_splits:
            self.n_splits = n_splits

        windows = self._generate_windows(len(data))
        scenarios = []

        for window in windows:
            test_data = data.iloc[window.test_start : window.test_end].copy()
            if not test_data.empty:
                scenarios.append(test_data)

        return scenarios

    def analyze(
        self,
        indicator: BaseIndicator,
        data: pd.DataFrame,
        metrics_calc: MetricsCalculator,
        target_metrics: dict[str, float],
    ) -> WalkForwardResult:
        """Run walk-forward analysis.

        Args:
            indicator: Indicator to test.
            data: OHLCV data.
            metrics_calc: Metrics calculator.
            target_metrics: Target metrics for passing.

        Returns:
            WalkForwardResult with all windows.
        """
        windows = self._generate_windows(len(data))
        results = []

        for window in windows:
            # Get train and test data
            train_data = data.iloc[window.train_start : window.train_end]
            test_data = data.iloc[window.test_start : window.test_end]

            # Optimize on training data (simplified - just calculate metrics)
            train_signals = indicator.generate_signals(train_data)
            train_metrics = metrics_calc.calculate_all(train_data, train_signals)
            window.train_metrics = train_metrics

            # Test on out-of-sample data
            test_signals = indicator.generate_signals(test_data)
            test_metrics = metrics_calc.calculate_all(test_data, test_signals)
            window.test_metrics = test_metrics

            # Check if test results meet targets
            window.passed = self._check_targets(test_metrics, target_metrics)
            results.append(window)

        # Aggregate results
        pass_rate = sum(1 for w in results if w.passed) / len(results) if results else 0
        avg_test = self._aggregate_metrics([w.test_metrics for w in results])
        efficiency = self._calculate_efficiency(results)

        result = WalkForwardResult(
            windows=results,
            overall_passed=pass_rate >= 0.6,  # 60% of windows must pass
            pass_rate=pass_rate,
            avg_test_performance=avg_test,
            efficiency_ratio=efficiency,
        )

        logger.info(
            f"Walk-forward: {pass_rate:.1%} pass rate, efficiency={efficiency:.2f}"
        )
        return result

    def _generate_windows(self, n_samples: int) -> list[WalkForwardWindow]:
        """Generate walk-forward windows.

        Args:
            n_samples: Total number of samples.

        Returns:
            List of WalkForwardWindow objects.
        """
        windows = []
        window_size = n_samples // self.n_splits
        train_size = int(window_size * self.train_pct)

        for i in range(self.n_splits):
            if self.anchored:
                # Anchored: train always starts from 0
                train_start = 0
                train_end = (i + 1) * window_size
                test_start = train_end
                test_end = min(test_start + window_size - train_size, n_samples)
            else:
                # Rolling: train window moves forward
                train_start = i * window_size
                train_end = train_start + train_size
                test_start = train_end
                test_end = min(train_start + window_size, n_samples)

            if test_start < test_end:
                windows.append(
                    WalkForwardWindow(
                        window_idx=i,
                        train_start=train_start,
                        train_end=train_end,
                        test_start=test_start,
                        test_end=test_end,
                    )
                )

        return windows

    def _check_targets(
        self,
        metrics: dict[str, float],
        targets: dict[str, float],
    ) -> bool:
        """Check if metrics meet targets.

        Args:
            metrics: Calculated metrics.
            targets: Target values.

        Returns:
            True if all targets are met.
        """
        for metric_name, target_value in targets.items():
            if metric_name not in metrics:
                continue

            actual = metrics[metric_name]

            # Handle metrics that should be less than target
            if metric_name in ["max_drawdown", "consecutive_losses"]:
                if actual > target_value:
                    return False
            else:
                if actual < target_value:
                    return False

        return True

    def _aggregate_metrics(self, metrics_list: list[dict]) -> dict:
        """Aggregate metrics across windows.

        Args:
            metrics_list: List of metrics dictionaries.

        Returns:
            Aggregated metrics.
        """
        if not metrics_list:
            return {}

        aggregated = {}
        all_keys: set[str] = set()
        for m in metrics_list:
            all_keys.update(m.keys())

        for key in all_keys:
            values = [m.get(key) for m in metrics_list if key in m]
            if values and all(isinstance(v, (int, float)) for v in values):
                aggregated[key] = {
                    "mean": float(np.mean(values)),
                    "std": float(np.std(values)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                }

        return aggregated

    def _calculate_efficiency(
        self,
        windows: list[WalkForwardWindow],
    ) -> float:
        """Calculate walk-forward efficiency ratio.

        Efficiency = out-of-sample performance / in-sample performance.

        Args:
            windows: List of walk-forward windows.

        Returns:
            Efficiency ratio (ideally close to 1.0).
        """
        if not windows:
            return 0.0

        train_pf = []
        test_pf = []

        for w in windows:
            if "profit_factor" in w.train_metrics and "profit_factor" in w.test_metrics:
                train_pf.append(w.train_metrics["profit_factor"])
                test_pf.append(w.test_metrics["profit_factor"])

        if not train_pf or np.mean(train_pf) == 0:
            return 0.0

        return float(np.mean(test_pf) / np.mean(train_pf))
