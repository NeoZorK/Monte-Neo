"""Unit tests for indicators."""

import pytest

from monte_neo.indicators.custom import CustomIndicatorBuilder
from monte_neo.indicators.technical import MACDIndicator, RSIIndicator, SMAIndicator


def test_sma_indicator(sample_ohlcv):
    ind = SMAIndicator()
    ind.set_parameters({"fast_period": 5, "slow_period": 10})

    # Test calculation
    calc = ind.calculate(sample_ohlcv)
    assert "sma_fast" in calc.columns
    assert "sma_slow" in calc.columns
    assert calc["sma_fast"].iloc[4] == pytest.approx(
        sample_ohlcv["close"].iloc[0:5].mean()
    )

    # Test signals
    signals = ind.generate_signals(sample_ohlcv)
    assert "signal" in signals.columns
    assert signals["signal"].isin([0, 1, -1]).all()

def test_rsi_indicator(sample_ohlcv):
    ind = RSIIndicator()
    ind.set_parameters({"period": 10, "overbought": 70, "oversold": 30})

    calc = ind.calculate(sample_ohlcv)
    assert "rsi" in calc.columns

    signals = ind.generate_signals(sample_ohlcv)
    assert "signal" in signals.columns

def test_macd_indicator(sample_ohlcv):
    ind = MACDIndicator()
    ind.set_parameters({"fast": 12, "slow": 26, "signal": 9})

    calc = ind.calculate(sample_ohlcv)
    assert "macd" in calc.columns
    assert "macd_signal" in calc.columns
    assert "macd_histogram" in calc.columns

    signals = ind.generate_signals(sample_ohlcv)
    assert "signal" in signals.columns

def test_custom_indicator_builder(sample_ohlcv):
    builder = CustomIndicatorBuilder()
    builder.add_sma("sma1", 5)
    builder.add_sma("sma2", 10)
    builder.add_entry_rule("sma1", "crosses_above", "sma2")
    builder.add_exit_rule("sma1", "crosses_below", "sma2")

    ind = builder.build("MyTestInd")
    assert ind.name == "MyTestInd"

    calc = ind.calculate(sample_ohlcv)
    assert "sma1" in calc.columns
    assert "sma2" in calc.columns

    signals = ind.generate_signals(sample_ohlcv)
    assert "signal" in signals.columns
