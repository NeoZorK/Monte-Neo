"""Drawdown metrics.

Calculates maximum drawdown and related metrics.
"""

from __future__ import annotations

import numpy as np

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class DrawdownMetric:
    """Drawdown calculator."""

    def calculate_max(self, equity: list[float] | np.ndarray) -> float:
        """Calculate maximum drawdown.

        Max Drawdown = (Peak - Trough) / Peak
        
        Args:
            equity: Equity curve values.

        Returns:
            Maximum drawdown as decimal (e.g., 0.20 = 20%).
        """
        if not len(equity):
            return 0.0

        equity = np.array(equity)
        
        # Running maximum
        running_max = np.maximum.accumulate(equity)
        
        # Drawdown at each point
        drawdowns = (running_max - equity) / running_max
        
        return float(np.max(drawdowns))

    def calculate_avg(self, equity: list[float] | np.ndarray) -> float:
        """Calculate average drawdown.

        Args:
            equity: Equity curve values.

        Returns:
            Average drawdown as decimal.
        """
        if not len(equity):
            return 0.0

        equity = np.array(equity)
        running_max = np.maximum.accumulate(equity)
        drawdowns = (running_max - equity) / running_max
        
        # Only count non-zero drawdowns
        dd_values = drawdowns[drawdowns > 0]
        
        if len(dd_values) == 0:
            return 0.0
        
        return float(np.mean(dd_values))

    def calculate_duration(self, equity: list[float] | np.ndarray) -> int:
        """Calculate maximum drawdown duration.

        Args:
            equity: Equity curve values.

        Returns:
            Maximum number of periods in drawdown.
        """
        if not len(equity):
            return 0

        equity = np.array(equity)
        running_max = np.maximum.accumulate(equity)
        
        # Find where we're in drawdown
        in_drawdown = equity < running_max
        
        # Count consecutive drawdown periods
        max_duration = 0
        current_duration = 0
        
        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0
        
        return max_duration

    def get_drawdown_curve(
        self,
        equity: list[float] | np.ndarray,
    ) -> np.ndarray:
        """Get the full drawdown curve.

        Args:
            equity: Equity curve values.

        Returns:
            Array of drawdown values at each point.
        """
        if not len(equity):
            return np.array([])

        equity = np.array(equity)
        running_max = np.maximum.accumulate(equity)
        drawdowns = (running_max - equity) / running_max
        
        return drawdowns

    def get_underwater_curve(
        self,
        equity: list[float] | np.ndarray,
    ) -> np.ndarray:
        """Get underwater curve (negative drawdowns).

        Args:
            equity: Equity curve values.

        Returns:
            Array of negative drawdown values.
        """
        return -self.get_drawdown_curve(equity)

    def analyze_drawdowns(
        self,
        equity: list[float] | np.ndarray,
        n_worst: int = 5,
    ) -> list[dict]:
        """Analyze worst drawdown periods.

        Args:
            equity: Equity curve values.
            n_worst: Number of worst drawdowns to return.

        Returns:
            List of drawdown info dictionaries.
        """
        if not len(equity):
            return []

        equity = np.array(equity)
        running_max = np.maximum.accumulate(equity)
        drawdowns = (running_max - equity) / running_max
        
        # Find drawdown periods
        periods = []
        in_dd = False
        start_idx = 0
        peak_val = 0
        
        for i, (dd, eq, peak) in enumerate(zip(drawdowns, equity, running_max)):
            if dd > 0 and not in_dd:
                # Start of drawdown
                in_dd = True
                start_idx = i
                peak_val = peak
            elif dd == 0 and in_dd:
                # End of drawdown
                in_dd = False
                periods.append({
                    "start_idx": start_idx,
                    "end_idx": i,
                    "duration": i - start_idx,
                    "max_drawdown": float(np.max(drawdowns[start_idx:i])),
                    "peak_value": float(peak_val),
                    "trough_value": float(np.min(equity[start_idx:i])),
                })
        
        # Handle ongoing drawdown
        if in_dd:
            periods.append({
                "start_idx": start_idx,
                "end_idx": len(equity) - 1,
                "duration": len(equity) - start_idx,
                "max_drawdown": float(np.max(drawdowns[start_idx:])),
                "peak_value": float(peak_val),
                "trough_value": float(np.min(equity[start_idx:])),
            })
        
        # Sort by max_drawdown and return worst N
        periods.sort(key=lambda x: x["max_drawdown"], reverse=True)
        return periods[:n_worst]
