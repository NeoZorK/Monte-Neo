"""Unified metrics calculator.

Calculates all trading metrics from signals and data.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numba import njit

from monte_neo.metrics.drawdown import DrawdownMetric
from monte_neo.metrics.profit_factor import ProfitFactorMetric
from monte_neo.metrics.sharpe import SharpeRatioMetric, SortinoRatioMetric
from monte_neo.metrics.winrate import WinrateMetric
from monte_neo.utils.logger import get_logger

try:
    from monte_neo.core import native_metrics  # type: ignore

    HAS_NATIVE = True
except ImportError:
    HAS_NATIVE = False

logger = get_logger(__name__)


@dataclass
class TradeResult:
    """Single trade result."""

    entry_idx: int
    exit_idx: int
    entry_price: float
    exit_price: float
    direction: int  # 1 = long, -1 = short
    pnl: float
    pnl_pct: float


class MetricsCalculator:
    """Calculate all trading metrics."""

    def __init__(self, risk_free_rate: float = 0.0) -> None:
        """Initialize metrics calculator.

        Args:
            risk_free_rate: Annual risk-free rate for Sharpe calculation.
        """
        self.risk_free_rate = risk_free_rate

        # Initialize individual metric calculators
        self.profit_factor = ProfitFactorMetric()
        self.sharpe = SharpeRatioMetric(risk_free_rate)
        self.sortino = SortinoRatioMetric(risk_free_rate)
        self.drawdown = DrawdownMetric()
        self.winrate = WinrateMetric()

    def calculate_all(
        self,
        data: pd.DataFrame,
        signals: pd.DataFrame,
    ) -> dict[str, float]:
        """Calculate all metrics.

        Args:
            data: OHLCV DataFrame.
            signals: DataFrame with entry/exit signals.

        Returns:
            Dictionary of all metrics.
        """
        # Extract trades from signals
        trades = self._extract_trades(data, signals)

        if not trades:
            return self._empty_metrics()

        # Calculate equity curve
        equity = self._calculate_equity(trades)
        returns = np.diff(equity) / equity[:-1] if len(equity) > 1 else []

        # Calculate individual metrics
        pnls = [t.pnl for t in trades]
        pnl_pcts = [t.pnl_pct for t in trades]

        metrics = {
            # Profit metrics
            "profit_factor": self.profit_factor.calculate(pnls),
            "total_return": float(np.sum(pnl_pcts)),
            "avg_return": float(np.mean(pnl_pcts)) if pnl_pcts else 0,
            # Risk-adjusted metrics
            "sharpe_ratio": self.sharpe.calculate(returns),
            "sortino_ratio": self.sortino.calculate(returns),
            # Drawdown metrics
            "max_drawdown": self.drawdown.calculate_max(equity),
            "avg_drawdown": self.drawdown.calculate_avg(equity),
            "recovery_factor": self._recovery_factor(pnl_pcts, equity),
            "calmar_ratio": self._calmar_ratio(pnl_pcts, equity),
            # Win/loss metrics
            "winrate": self.winrate.calculate(pnls),
            "expectancy": self.winrate.expectancy(pnls),
            "avg_win": self.winrate.avg_win(pnls),
            "avg_loss": self.winrate.avg_loss(pnls),
            "win_loss_ratio": self.winrate.win_loss_ratio(pnls),
            # Trade statistics
            "trade_count": len(trades),
            "consecutive_wins": self._max_consecutive(pnls, True),
            "consecutive_losses": self._max_consecutive(pnls, False),
        }

        return metrics

    def _extract_trades(
        self,
        data: pd.DataFrame,
        signals: pd.DataFrame,
    ) -> list[TradeResult]:
        """Extract trades from signals. Use C++ if available."""
        if "signal" not in signals.columns:
            return []

        # Convert to numpy for maximum speed
        close_prices = data["close"].to_numpy()
        signal_array = signals["signal"].to_numpy().astype(np.int32)

        if HAS_NATIVE:
            # Use high-performance C++ extension
            raw_trades = native_metrics.extract_trades(
                close_prices.tolist(),  # pybind11 might need list if not using numpy bindings
                signal_array.tolist(),
            )
            return [
                TradeResult(
                    entry_idx=t.entry_idx,
                    exit_idx=t.exit_idx,
                    entry_price=t.entry_price,
                    exit_price=t.exit_price,
                    direction=t.direction,
                    pnl=t.pnl,
                    pnl_pct=t.pnl_pct,
                )
                for t in raw_trades
            ]

        # Fallback to JIT-compiled Python
        raw_trades = self._extract_trades_fast(close_prices, signal_array)

        return [TradeResult(*t) for t in raw_trades]

    @staticmethod
    @njit
    def _extract_trades_fast(
        prices: np.ndarray, signals: np.ndarray
    ) -> list[tuple[int, int, float, float, int, float, float]]:
        """Fast trade extraction using Numba JIT.

        Note: Numba works best with primitive types, so we return a list of tuples
        and convert to TradeResult objects in the wrapper.
        """
        results = []

        position = 0
        entry_idx = 0
        entry_price = 0.0

        for i in range(len(signals)):
            signal = signals[i]
            price = prices[i]

            if position == 0:
                if signal != 0:
                    # Open position
                    position = int(signal)
                    entry_idx = i
                    entry_price = price
            elif signal == -position:
                # Close position
                exit_price = price
                pnl = (exit_price - entry_price) * position
                pnl_pct = pnl / entry_price

                results.append(
                    (entry_idx, i, entry_price, exit_price, position, pnl, pnl_pct)
                )

                # Reset position
                position = 0

        return results

    def _calculate_equity(self, trades: list[TradeResult]) -> np.ndarray:
        """Calculate equity curve from trades using vectorized cumprod."""
        if not trades:
            return np.array([1.0])

        pnl_pcts = np.array([t.pnl_pct for t in trades])
        # Equity starts at 1.0, then cumprod of (1 + pnl_pct)
        equity = np.ones(len(trades) + 1)
        equity[1:] = np.cumprod(1 + pnl_pcts)

        return equity

    def _recovery_factor(
        self,
        pnl_pcts: list[float],
        equity: np.ndarray,
    ) -> float:
        """Calculate recovery factor.

        Args:
            pnl_pcts: List of P&L percentages.
            equity: Equity curve.

        Returns:
            Recovery factor (total_return / max_drawdown).
        """
        total_return = np.sum(pnl_pcts)
        max_dd = self.drawdown.calculate_max(equity)

        if max_dd == 0:
            return 0.0

        return float(total_return / max_dd)

    def _calmar_ratio(
        self,
        pnl_pcts: list[float],
        equity: np.ndarray,
        periods_per_year: int = 252,
    ) -> float:
        """Calculate Calmar ratio.

        Args:
            pnl_pcts: List of P&L percentages.
            equity: Equity curve.
            periods_per_year: Trading periods per year.

        Returns:
            Calmar ratio (annual_return / max_drawdown).
        """
        max_dd = self.drawdown.calculate_max(equity)

        if max_dd == 0 or not pnl_pcts:
            return 0.0

        # Annualize returns (simplified)
        avg_return = np.mean(pnl_pcts)
        annual_return = avg_return * periods_per_year

        return float(annual_return / max_dd)

    def _max_consecutive(self, pnls: list[float], wins: bool) -> int:
        """Calculate max consecutive wins or losses.

        Args:
            pnls: List of P&L values.
            wins: If True, count wins; else count losses.

        Returns:
            Maximum consecutive count.
        """
        max_count = 0
        current = 0

        for pnl in pnls:
            is_win = pnl > 0
            if is_win == wins:
                current += 1
                max_count = max(max_count, current)
            else:
                current = 0

        return max_count

    def _empty_metrics(self) -> dict[str, float]:
        """Return empty metrics when no trades."""
        return {
            "profit_factor": 0,
            "total_return": 0,
            "avg_return": 0,
            "sharpe_ratio": 0,
            "sortino_ratio": 0,
            "max_drawdown": 0,
            "avg_drawdown": 0,
            "recovery_factor": 0,
            "calmar_ratio": 0,
            "winrate": 0,
            "expectancy": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "win_loss_ratio": 0,
            "trade_count": 0,
            "consecutive_wins": 0,
            "consecutive_losses": 0,
        }
