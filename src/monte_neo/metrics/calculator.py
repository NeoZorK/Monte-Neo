"""Unified metrics calculator.

Calculates all trading metrics from signals and data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.core import native_metrics  # type: ignore
from monte_neo.metrics import numba_funcs
from monte_neo.metrics import utils as metric_utils
from monte_neo.metrics.drawdown import DrawdownMetric
from monte_neo.metrics.profit_factor import ProfitFactorMetric
from monte_neo.metrics.sharpe import SharpeRatioMetric, SortinoRatioMetric
from monte_neo.metrics.types import TradeResult
from monte_neo.metrics.winrate import WinrateMetric
from monte_neo.utils.logger import get_logger

try:
    # Check if native module is available and working
    native_metrics.extract_trades
    HAS_NATIVE = True
except (ImportError, AttributeError):
    HAS_NATIVE = False

logger = get_logger(__name__)


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
        data: pd.DataFrame | np.ndarray,
        signals: pd.DataFrame | np.ndarray,
        required_metrics: list[str] | None = None,
        use_sl_tp: bool = False,
        sl_pct: float = 0.0,
        tp_pct: float = 0.0,
    ) -> dict[str, float]:
        """Calculate metrics.

        Args:
            data: OHLCV DataFrame or numpy array (OHLCV).
            signals: DataFrame with 'signal' column or numpy array of signals.
            required_metrics: Optional list of metrics to calculate. If None, calculate all.
            use_sl_tp: Whether to apply Stop Loss and Take Profit.
            sl_pct: Stop Loss percentage (e.g., 1.0 for 1%).
            tp_pct: Take Profit percentage (e.g., 2.0 for 2%).

        Returns:
            Dictionary of metrics.
        """
        # Extract trades from signals
        trades = self._extract_trades(data, signals, use_sl_tp, sl_pct, tp_pct)

        if not trades:
            return metric_utils.get_empty_metrics()

        # Basic PnLs are needed for almost everything
        pnls = [t.pnl for t in trades]
        pnl_pcts = [t.pnl_pct for t in trades]

        metrics = {}

        # If required_metrics is provided, check what we need
        need_all = required_metrics is None
        reqs = set(required_metrics) if required_metrics else set()

        def needs(name: str) -> bool:
            return need_all or name in reqs

        # Profit metrics
        if needs("profit_factor"):
            metrics["profit_factor"] = self.profit_factor.calculate(pnls)
        if needs("total_return"):
            metrics["total_return"] = float(np.sum(pnl_pcts))
        if needs("avg_return"):
            metrics["avg_return"] = float(np.mean(pnl_pcts)) if pnl_pcts else 0.0
        if needs("winrate"):
            metrics["winrate"] = self.winrate.calculate(pnls)
        if needs("expectancy"):
            metrics["expectancy"] = self.winrate.expectancy(pnls)
        if needs("avg_win"):
            metrics["avg_win"] = self.winrate.avg_win(pnls)
        if needs("avg_loss"):
            metrics["avg_loss"] = self.winrate.avg_loss(pnls)
        if needs("win_loss_ratio"):
            metrics["win_loss_ratio"] = self.winrate.win_loss_ratio(pnls)
        if needs("trade_count"):
            metrics["trade_count"] = len(trades)
        if needs("consecutive_wins"):
            metrics["consecutive_wins"] = metric_utils.max_consecutive(pnls, True)
        if needs("consecutive_losses"):
            metrics["consecutive_losses"] = metric_utils.max_consecutive(pnls, False)

        # Complex metrics requiring Equity Curve
        equity_metrics = {
            "sharpe_ratio",
            "sortino_ratio",
            "max_drawdown",
            "avg_drawdown",
            "recovery_factor",
            "calmar_ratio",
        }

        if need_all or not reqs.isdisjoint(equity_metrics):
            equity = self._calculate_equity(trades)
            max_dd_val = 0.0

            if (
                needs("max_drawdown")
                or needs("recovery_factor")
                or needs("calmar_ratio")
            ):
                max_dd_val = self.drawdown.calculate_max(equity)
                if needs("max_drawdown"):
                    metrics["max_drawdown"] = max_dd_val

            if needs("avg_drawdown"):
                metrics["avg_drawdown"] = self.drawdown.calculate_avg(equity)

            if needs("recovery_factor"):
                total_ret = float(np.sum(pnl_pcts))
                metrics["recovery_factor"] = metric_utils.calculate_recovery_factor(
                    total_ret, max_dd_val
                )

            if needs("calmar_ratio"):
                avg_ret = float(np.mean(pnl_pcts)) if pnl_pcts else 0.0
                metrics["calmar_ratio"] = metric_utils.calculate_calmar_ratio(
                    avg_ret, max_dd_val
                )

            # Returns based metrics
            if needs("sharpe_ratio") or needs("sortino_ratio"):
                returns = np.diff(equity) / equity[:-1] if len(equity) > 1 else []

                if needs("sharpe_ratio"):
                    metrics["sharpe_ratio"] = self.sharpe.calculate(returns)
                if needs("sortino_ratio"):
                    metrics["sortino_ratio"] = self.sortino.calculate(returns)

        return metrics

    def _extract_trades(
        self,
        data: pd.DataFrame | np.ndarray,
        signals: pd.DataFrame | np.ndarray,
        use_sl_tp: bool = False,
        sl_pct: float = 0.0,
        tp_pct: float = 0.0,
    ) -> list[TradeResult]:
        """Extract trades from signals. Use C++ if available."""
        # Convert data to numpy arrays if it's a DataFrame
        if isinstance(data, pd.DataFrame):
            close_prices = data["close"].to_numpy()
            high_prices = data["high"].to_numpy()
            low_prices = data["low"].to_numpy()
        else:
            # Assume data is a numpy array (OHLCV)
            # col 1=high, 2=low, 3=close
            high_prices = data[:, 1]
            low_prices = data[:, 2]
            close_prices = data[:, 3]

        # Convert signals to numpy array if it's a DataFrame
        if isinstance(signals, pd.DataFrame):
            if "signal" not in signals.columns:
                return []
            signal_array = signals["signal"].to_numpy().astype(np.int32)
        else:
            signal_array = np.asarray(signals, dtype=np.int32)

        if HAS_NATIVE and not use_sl_tp:
            # Use high-performance C++ extension (native doesn't support SL/TP yet)
            raw_trades = native_metrics.extract_trades(
                close_prices.tolist(),
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
        raw_trades = numba_funcs.extract_trades_fast(
            close_prices,
            high_prices,
            low_prices,
            signal_array,
            use_sl_tp,
            sl_pct,
            tp_pct,
        )

        return [TradeResult(*t) for t in raw_trades]

    @staticmethod
    def calculate_batch_fast(
        prices: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        signal_matrix: np.ndarray,
        use_sl_tp: bool,
        sl_pct: float,
        tp_pct: float,
    ) -> np.ndarray:
        """Calculate basic metrics for a batch of signal sets in parallel."""
        return numba_funcs.calculate_batch_fast(
            prices, highs, lows, signal_matrix, use_sl_tp, sl_pct, tp_pct
        )

    @staticmethod
    def calculate_batch_multi_price_fast(
        price_matrix: np.ndarray,
        high_matrix: np.ndarray,
        low_matrix: np.ndarray,
        signal_matrix: np.ndarray,
        use_sl_tp: bool,
        sl_pct: float,
        tp_pct: float,
    ) -> np.ndarray:
        """Calculate basic metrics for a batch where each row has its own prices."""
        return numba_funcs.calculate_batch_multi_price_fast(
            price_matrix,
            high_matrix,
            low_matrix,
            signal_matrix,
            use_sl_tp,
            sl_pct,
            tp_pct,
        )

    def _calculate_equity(self, trades: list[TradeResult]) -> np.ndarray:
        """Calculate equity curve from trades using vectorized cumprod."""
        if not trades:
            return np.array([1.0])

        pnl_pcts = np.array([t.pnl_pct for t in trades])
        # Equity starts at 1.0, then cumprod of (1 + pnl_pct)
        equity = np.ones(len(trades) + 1)
        equity[1:] = np.cumprod(1 + pnl_pcts)

        return equity
