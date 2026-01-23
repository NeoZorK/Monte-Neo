"""Sharpe and Sortino ratio metrics.

Risk-adjusted return metrics for evaluating trading performance.
"""

from __future__ import annotations

import numpy as np

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class SharpeRatioMetric:
    """Sharpe Ratio calculator."""

    def __init__(
        self,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> None:
        """Initialize Sharpe calculator.

        Args:
            risk_free_rate: Annual risk-free rate.
            periods_per_year: Trading periods per year.
        """
        self.risk_free_rate = risk_free_rate
        self.periods_per_year = periods_per_year

    def calculate(self, returns: list[float] | np.ndarray) -> float:
        """Calculate Sharpe ratio.

        Sharpe = (Mean Return - Risk Free) / Std(Returns) * sqrt(periods)

        Values > 1 are good, > 2 are excellent.

        Args:
            returns: List of period returns.

        Returns:
            Annualized Sharpe ratio.
        """
        if not len(returns):
            return 0.0

        returns = np.array(returns)

        if len(returns) < 2 or np.std(returns) == 0:
            return 0.0

        # Convert annual risk-free to period risk-free
        period_rf = (1 + self.risk_free_rate) ** (1 / self.periods_per_year) - 1

        excess_returns = returns - period_rf
        mean_excess = np.mean(excess_returns)
        std_returns = np.std(returns, ddof=1)

        # Annualize
        sharpe = (mean_excess / std_returns) * np.sqrt(self.periods_per_year)

        return float(sharpe)

    def calculate_rolling(
        self,
        returns: list[float] | np.ndarray,
        window: int = 20,
    ) -> np.ndarray:
        """Calculate rolling Sharpe ratio.

        Args:
            returns: List of period returns.
            window: Rolling window size.

        Returns:
            Array of rolling Sharpe ratios.
        """
        if len(returns) < window:
            return np.array([self.calculate(returns)])

        returns = np.array(returns)
        rolling_sharpe = []

        for i in range(window, len(returns) + 1):
            window_returns = returns[i - window : i]
            rolling_sharpe.append(self.calculate(window_returns))

        return np.array(rolling_sharpe)


class SortinoRatioMetric:
    """Sortino Ratio calculator (downside risk adjusted)."""

    def __init__(
        self,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> None:
        """Initialize Sortino calculator.

        Args:
            risk_free_rate: Annual risk-free rate.
            periods_per_year: Trading periods per year.
        """
        self.risk_free_rate = risk_free_rate
        self.periods_per_year = periods_per_year

    def calculate(self, returns: list[float] | np.ndarray) -> float:
        """Calculate Sortino ratio.

        Sortino = (Mean Return - Risk Free) / Downside Deviation * sqrt(periods)

        Uses only negative returns for volatility calculation.

        Args:
            returns: List of period returns.

        Returns:
            Annualized Sortino ratio.
        """
        if not len(returns):
            return 0.0

        returns = np.array(returns)

        # Convert annual risk-free to period risk-free
        period_rf = (1 + self.risk_free_rate) ** (1 / self.periods_per_year) - 1

        excess_returns = returns - period_rf
        mean_excess = np.mean(excess_returns)

        # Downside deviation (only negative returns)
        downside_returns = returns[returns < 0]

        if len(downside_returns) < 2:
            return float("inf") if mean_excess > 0 else 0.0

        downside_std = np.std(downside_returns, ddof=1)

        if downside_std == 0:
            return float("inf") if mean_excess > 0 else 0.0

        # Annualize
        sortino = (mean_excess / downside_std) * np.sqrt(self.periods_per_year)

        return float(sortino)

    def calculate_downside_deviation(
        self,
        returns: list[float] | np.ndarray,
        target: float = 0,
    ) -> float:
        """Calculate downside deviation.

        Args:
            returns: List of period returns.
            target: Target return (default: 0).

        Returns:
            Downside deviation.
        """
        returns = np.array(returns)
        below_target = returns[returns < target]

        if len(below_target) < 2:
            return 0.0

        return float(np.std(below_target, ddof=1))
