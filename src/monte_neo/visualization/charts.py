"""Chart visualization module.

Generate charts for indicator visualization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class ChartGenerator:
    """Generate trading charts."""

    def __init__(self) -> None:
        """Initialize chart generator."""
        self._has_mplfinance = False
        try:
            import mplfinance  # noqa
            self._has_mplfinance = True
        except ImportError:
            logger.warning("mplfinance not available, using plotext")

    def plot_candlestick(
        self,
        data: pd.DataFrame,
        title: str = "Price Chart",
        save_path: str | None = None,
    ) -> None:
        """Plot candlestick chart.

        Args:
            data: OHLCV DataFrame.
            title: Chart title.
            save_path: Path to save image.
        """
        if self._has_mplfinance:
            self._plot_mpl(data, title, save_path)
        else:
            self._plot_terminal(data, title)

    def _plot_mpl(
        self,
        data: pd.DataFrame,
        title: str,
        save_path: str | None,
    ) -> None:
        """Plot with mplfinance."""
        import mplfinance as mpf
        
        # Prepare data
        df = data.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        kwargs = {
            "type": "candle",
            "volume": True,
            "title": title,
            "style": "charles",
            "figsize": (12, 8),
        }

        if save_path:
            kwargs["savefig"] = save_path
            mpf.plot(df, **kwargs)
        else:
            mpf.plot(df, **kwargs)

    def _plot_terminal(
        self,
        data: pd.DataFrame,
        title: str,
    ) -> None:
        """Plot in terminal with plotext."""
        import plotext as plt
        
        plt.clear_figure()
        plt.title(title)
        plt.plot(data["close"].values, label="Close")
        plt.show()

    def plot_with_signals(
        self,
        data: pd.DataFrame,
        signals: pd.DataFrame,
        title: str = "Chart with Signals",
    ) -> None:
        """Plot chart with entry/exit signals.

        Args:
            data: OHLCV DataFrame.
            signals: Signals DataFrame.
            title: Chart title.
        """
        import plotext as plt
        
        plt.clear_figure()
        plt.title(title)
        
        # Price
        close = data["close"].values
        plt.plot(close, label="Price")
        
        # Entry signals
        if "signal" in signals.columns:
            entries = signals["signal"] == 1
            exits = signals["signal"] == -1
            
            entry_idx = entries[entries].index.tolist()
            exit_idx = exits[exits].index.tolist()
            
            # Mark entries and exits
            for idx in entry_idx:
                if idx < len(close):
                    plt.scatter([idx], [close[idx]], marker="▲", color="green")
            
            for idx in exit_idx:
                if idx < len(close):
                    plt.scatter([idx], [close[idx]], marker="▼", color="red")
        
        plt.show()
