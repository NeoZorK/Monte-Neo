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

        # Use candlestick if OHLC data is available
        if all(col in data.columns for col in ["open", "high", "low", "close"]):
            if hasattr(data.index, "astype"):
                dates = data.index.astype(str).tolist()
            else:
                dates = list(range(len(data)))
            # Plotext expects lists
            plt.candlestick(
                dates,
                data["open"].tolist(),
                data["high"].tolist(),
                data["low"].tolist(),
                data["close"].tolist(),
                label="OHLC",
                orientation="vertical"
            )
        else:
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
        if signals is not None:
            # Normalize signals to Series if it's a dict or DataFrame
            if isinstance(signals, dict):
                sig_series = pd.Series(signals.get("signal", 0), index=data.index)
            elif isinstance(signals, pd.DataFrame):
                sig_series = signals["signal"] if "signal" in signals.columns else signals.iloc[:, 0]
            else:
                sig_series = pd.Series(signals, index=data.index)

            entries = sig_series == 1
            exits = sig_series == -1

            # Mark entries and exits
            for i in range(len(sig_series)):
                if entries.iloc[i]:
                    plt.scatter([i], [close[i]], marker="▲", color="green")
                elif exits.iloc[i]:
                    plt.scatter([i], [close[i]], marker="▼", color="red")

        plt.show()
