"""Winrate and expectancy metrics.

Calculates win rate, expectancy, and related statistics.
"""

from __future__ import annotations

import numpy as np

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class WinrateMetric:
    """Winrate and expectancy calculator."""

    def calculate(self, pnls: list[float] | np.ndarray) -> float:
        """Calculate win rate.

        Win Rate = Winning Trades / Total Trades

        Args:
            pnls: List of P&L values.

        Returns:
            Win rate as decimal (e.g., 0.60 = 60%).
        """
        if not len(pnls):
            return 0.0

        pnls = np.array(pnls)
        winners = np.sum(pnls > 0)
        
        return float(winners / len(pnls))

    def expectancy(self, pnls: list[float] | np.ndarray) -> float:
        """Calculate expectancy (expected value per trade).

        Expectancy = (Winrate × Avg Win) - ((1 - Winrate) × Avg Loss)
        
        Positive expectancy indicates profitable system.

        Args:
            pnls: List of P&L values.

        Returns:
            Expected value per trade.
        """
        if not len(pnls):
            return 0.0

        pnls = np.array(pnls)
        
        winrate = self.calculate(pnls)
        avg_win = self.avg_win(pnls)
        avg_loss = self.avg_loss(pnls)
        
        expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss)
        
        return float(expectancy)

    def avg_win(self, pnls: list[float] | np.ndarray) -> float:
        """Calculate average winning trade.

        Args:
            pnls: List of P&L values.

        Returns:
            Average win value.
        """
        if not len(pnls):
            return 0.0

        pnls = np.array(pnls)
        winners = pnls[pnls > 0]
        
        if len(winners) == 0:
            return 0.0
        
        return float(np.mean(winners))

    def avg_loss(self, pnls: list[float] | np.ndarray) -> float:
        """Calculate average losing trade (as positive value).

        Args:
            pnls: List of P&L values.

        Returns:
            Average loss value (positive).
        """
        if not len(pnls):
            return 0.0

        pnls = np.array(pnls)
        losers = pnls[pnls < 0]
        
        if len(losers) == 0:
            return 0.0
        
        return float(abs(np.mean(losers)))

    def win_loss_ratio(self, pnls: list[float] | np.ndarray) -> float:
        """Calculate average win / average loss ratio.

        Also known as reward-to-risk ratio.

        Args:
            pnls: List of P&L values.

        Returns:
            Win/loss ratio.
        """
        avg_win = self.avg_win(pnls)
        avg_loss = self.avg_loss(pnls)
        
        if avg_loss == 0:
            return float("inf") if avg_win > 0 else 0.0
        
        return float(avg_win / avg_loss)

    def required_winrate(self, reward_risk_ratio: float) -> float:
        """Calculate required winrate for breakeven.

        Args:
            reward_risk_ratio: Reward-to-risk ratio.

        Returns:
            Breakeven win rate.
        """
        if reward_risk_ratio <= 0:
            return 1.0
        
        return 1 / (1 + reward_risk_ratio)

    def edge_ratio(self, pnls: list[float] | np.ndarray) -> float:
        """Calculate edge ratio.

        Edge = Actual Winrate - Required Winrate

        Args:
            pnls: List of P&L values.

        Returns:
            Edge ratio (positive = profitable edge).
        """
        winrate = self.calculate(pnls)
        rr_ratio = self.win_loss_ratio(pnls)
        required = self.required_winrate(rr_ratio)
        
        return float(winrate - required)

    def get_trade_distribution(
        self,
        pnls: list[float] | np.ndarray,
    ) -> dict:
        """Get trade P&L distribution statistics.

        Args:
            pnls: List of P&L values.

        Returns:
            Distribution statistics.
        """
        if not len(pnls):
            return {
                "count": 0,
                "winners": 0,
                "losers": 0,
                "breakeven": 0,
            }

        pnls = np.array(pnls)
        
        return {
            "count": len(pnls),
            "winners": int(np.sum(pnls > 0)),
            "losers": int(np.sum(pnls < 0)),
            "breakeven": int(np.sum(pnls == 0)),
            "best_trade": float(np.max(pnls)),
            "worst_trade": float(np.min(pnls)),
            "median": float(np.median(pnls)),
            "std": float(np.std(pnls)),
            "skew": float(self._skewness(pnls)),
        }

    def _skewness(self, data: np.ndarray) -> float:
        """Calculate skewness of distribution.

        Args:
            data: Data array.

        Returns:
            Skewness value.
        """
        if len(data) < 3:
            return 0.0
        
        mean = np.mean(data)
        std = np.std(data)
        
        if std == 0:
            return 0.0
        
        return float(np.mean(((data - mean) / std) ** 3))
