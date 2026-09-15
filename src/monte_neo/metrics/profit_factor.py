"""Profit Factor metric.

Calculates the ratio of gross profits to gross losses.
"""

from __future__ import annotations

import numpy as np

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class ProfitFactorMetric:
    """Profit Factor calculator."""

    def calculate(self, pnls: list[float] | np.ndarray) -> float:
        """Calculate profit factor.

        Profit Factor = Gross Profit / Gross Loss

        Values > 1 indicate profitability.
        Values > 2 are considered excellent.

        Args:
            pnls: List of P&L values.

        Returns:
            Profit factor value.
        """
        if not len(pnls):
            return 0.0

        pnls = np.array(pnls)

        gross_profit = np.sum(pnls[pnls > 0])
        gross_loss = abs(np.sum(pnls[pnls < 0]))

        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0

        return float(gross_profit / gross_loss)

    def calculate_rolling(
        self,
        pnls: list[float] | np.ndarray,
        window: int = 20,
    ) -> np.ndarray:
        """Calculate rolling profit factor.

        Args:
            pnls: List of P&L values.
            window: Rolling window size.

        Returns:
            Array of rolling profit factors.
        """
        if len(pnls) < window:
            return np.array([self.calculate(pnls)])

        pnls = np.array(pnls)
        rolling_pf = []

        for i in range(window, len(pnls) + 1):
            window_pnls = pnls[i - window : i]
            rolling_pf.append(self.calculate(window_pnls))

        return np.array(rolling_pf)

    def is_acceptable(
        self,
        pnls: list[float] | np.ndarray,
        threshold: float = 1.5,
    ) -> bool:
        """Check if profit factor meets threshold.

        Args:
            pnls: List of P&L values.
            threshold: Minimum acceptable profit factor.

        Returns:
            True if profit factor >= threshold.
        """
        return self.calculate(pnls) >= threshold
