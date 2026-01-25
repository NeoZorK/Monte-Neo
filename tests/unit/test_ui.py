"""Unit tests for UI components (CLI and Visualization)."""

from unittest.mock import patch

import pandas as pd

from monte_neo.cli.progress import ProgressTracker
from monte_neo.visualization.charts import ChartGenerator
from monte_neo.visualization.metrics import MetricsDisplay
from monte_neo.visualization.trades import TradeVisualizer


def test_price_chart(sample_ohlcv):
    # Mock plotext and mplfinance
    with (
        patch("plotext.show") as mock_show_terminal,
        patch("plotext.candlestick") as mock_candle,
        patch("mplfinance.plot") as mock_show_mpl,
    ):
        chart = ChartGenerator()
        # Test drawing without signals
        chart.plot_candlestick(sample_ohlcv)
        assert mock_candle.called or mock_show_mpl.called

        # Test with signals
        signals = pd.DataFrame({"signal": [0] * 100}, index=sample_ohlcv.index)
        signals.iloc[5] = 1
        signals.iloc[10] = -1
        chart.plot_with_signals(sample_ohlcv, signals)
        assert mock_show_terminal.called or mock_show_mpl.called


def test_metrics_visualizer():
    with patch("rich.console.Console.print") as mock_print:
        viz = MetricsDisplay()
        metrics = {"profit_factor": 2.5, "sharpe_ratio": 1.2, "max_drawdown": 0.15}
        viz.show_metrics_table(metrics)
        assert mock_print.called


def test_trade_visualizer(sample_ohlcv):
    from monte_neo.metrics.calculator import MetricsCalculator

    with patch("rich.table.Table.add_row") as mock_add_row:
        viz = TradeVisualizer()
        calc = MetricsCalculator()
        # Mock signals that produce trades
        signals = pd.DataFrame({"signal": [0] * 100}, index=sample_ohlcv.index)
        signals.iloc[5, 0] = 1
        signals.iloc[10, 0] = -1

        # Use protected method for testing
        trades = calc._extract_trades(sample_ohlcv, signals)

        viz.show_trades_table(trades)
        assert mock_add_row.called


def test_progress_tracker():
    with patch("rich.progress.Progress.update"):
        mgr = ProgressTracker()
        mgr.start(100)
        # Assumingmgr uses rich progress internally or similar
        # If it's a simple rich progress wrapper:
        mgr.update(10, 100, "Working...")
        mgr.stop()
        # Just verify it doesn't crash for now if we don't know internals
