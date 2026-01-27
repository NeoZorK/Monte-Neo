
import numpy as np
import pandas as pd
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.metrics.types import TradeResult
from monte_neo.indicators.sma import SMAIndicator
from monte_neo.indicators.rsi import RSIIndicator
from monte_neo.indicators.macd import MACDIndicator
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.indicators.base import IndicatorConfig

def create_mock_data(n=1000):
    np.random.seed(42)
    # Generate some price data with trends and reversals
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + 0.5
    low = close - 0.5
    open_p = close + 0.1
    volume = np.random.rand(n) * 1000
    
    return pd.DataFrame({
        'open': open_p,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })

def test_sl_tp_logic():
    print("Testing SL/TP Logic Accuracy...")
    calc = MetricsCalculator()
    
    # 1. Manually construct data to trigger SL
    # Entry at 100, SL at 1% (99), High stays below TP
    data = pd.DataFrame({
        'open':  [100, 100, 100],
        'high':  [100.5, 100.5, 100.5],
        'low':   [99.5, 98.5, 99.5], # Low hits 98.5 at index 1
        'close': [100, 99, 99],
        'volume': [100, 100, 100]
    })
    signals = np.array([1, 0, 0]) # Buy at index 0
    
    # SL = 1%, TP = 5%
    metrics = calc.calculate_all(data, signals, use_sl_tp=True, sl_pct=1.0, tp_pct=5.0)
    
    # Extract trades directly to verify indices
    trades = calc._extract_trades(data, signals, use_sl_tp=True, sl_pct=1.0, tp_pct=5.0)
    
    print(f"SL Test (Entry 100, SL 1%):")
    if len(trades) > 0:
        t = trades[0]
        print(f"  Entry Price: {t.entry_price}, Exit Price: {t.exit_price}")
        print(f"  Entry Idx: {t.entry_idx}, Exit Idx: {t.exit_idx}")
        print(f"  PnL %: {t.pnl_pct:.4f}")
        
        # Expected: Exit at 99.0 (100 * 0.99) at index 1
        assert t.exit_price == 99.0, f"Expected 99.0, got {t.exit_price}"
        assert t.exit_idx == 1, f"Expected index 1, got {t.exit_idx}"
        assert t.pnl_pct == -0.01, f"Expected -0.01, got {t.pnl_pct}"
        print("  ✅ SL Logic Correct")
    else:
        print("  ❌ No trades detected")

    # 2. Manually construct data to trigger TP
    data_tp = pd.DataFrame({
        'open':  [100, 100, 100],
        'high':  [100.5, 106.0, 100.5], # High hits 106 at index 1
        'low':   [99.5, 99.5, 99.5],
        'close': [100, 105, 105],
        'volume': [100, 100, 100]
    })
    
    metrics_tp = calc.calculate_all(data_tp, signals, use_sl_tp=True, sl_pct=5.0, tp_pct=5.0)
    trades_tp = calc._extract_trades(data_tp, signals, use_sl_tp=True, sl_pct=5.0, tp_pct=5.0)
    
    print(f"TP Test (Entry 100, TP 5%):")
    if len(trades_tp) > 0:
        t = trades_tp[0]
        print(f"  Entry Price: {t.entry_price}, Exit Price: {t.exit_price}")
        print(f"  Entry Idx: {t.entry_idx}, Exit Idx: {t.exit_idx}")
        print(f"  PnL %: {t.pnl_pct:.4f}")
        
        # Expected: Exit at 105.0 (100 * 1.05) at index 1
        assert t.exit_price == 105.0, f"Expected 105.0, got {t.exit_price}"
        assert t.exit_idx == 1, f"Expected index 1, got {t.exit_idx}"
        assert t.pnl_pct == 0.05, f"Expected 0.05, got {t.pnl_pct}"
        print("  ✅ TP Logic Correct")
    else:
        print("  ❌ No trades detected")

def test_indicator_signals():
    print("\nTesting Indicator Signals...")
    data = create_mock_data(200)
    
    indicators = [
        SMAIndicator(IndicatorConfig(name="SMA", parameters={'fast_period': 5, 'slow_period': 10})),
        RSIIndicator(IndicatorConfig(name="RSI", parameters={'period': 14, 'overbought': 70, 'oversold': 30})),
        MACDIndicator(IndicatorConfig(name="MACD", parameters={'fast': 12, 'slow': 26, 'signal': 9})),
        DynamicIndicator(IndicatorConfig(name="Dynamic", parameters={'source_code': "data['close'].diff() > 0"}))
    ]
    
    for ind in indicators:
        signals = ind.generate_signals_fast(data)
        unique_signals = np.unique(signals)
        print(f"  Indicator: {ind.name}")
        print(f"    Unique signals: {unique_signals}")
        print(f"    Total signals: {len(signals)}")
        assert len(signals) == len(data)
        assert all(s in [-1, 0, 1] for s in unique_signals)
        
    print("  ✅ Indicator Signals Correct")

if __name__ == "__main__":
    try:
        test_sl_tp_logic()
        test_indicator_signals()
        print("\nAll verification tests PASSED! 🚀")
    except AssertionError as e:
        print(f"\n❌ Verification failed: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
