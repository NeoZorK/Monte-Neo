"""Unit tests for metrics calculation."""

from monte_neo.metrics.calculator import MetricsCalculator


def test_metrics_calculator_init():
    calc = MetricsCalculator(risk_free_rate=0.02)
    assert calc.risk_free_rate == 0.02


def test_calculate_all(sample_ohlcv, sample_signals):
    calc = MetricsCalculator()
    metrics = calc.calculate_all(sample_ohlcv, sample_signals)

    assert "profit_factor" in metrics
    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics
    assert "winrate" in metrics
    assert metrics["trade_count"] == 2


def test_profit_factor_calculation():
    calc = MetricsCalculator()
    # 2 wins of 100, 1 loss of 50 => PF = 200/50 = 4.0
    pnls = [100.0, 100.0, -50.0]
    pf = calc.profit_factor.calculate(pnls)
    assert pf == 4.0


def test_max_drawdown():
    calc = MetricsCalculator()
    equity = [100, 110, 120, 90, 130]  # Peak 120, Trough 90 -> DD = 30/120 = 0.25
    dd = calc.drawdown.calculate_max(equity)
    assert dd == 0.25


def test_sl_tp_extraction():
    """Test that Stop Loss and Take Profit are correctly applied."""
    import pandas as pd
    import numpy as np

    calc = MetricsCalculator()
    
    # Create custom data where SL and TP will be hit
    dates = pd.date_range(start="2024-01-01", periods=10, freq="1h")
    data = pd.DataFrame({
        "open":  [100, 101, 102, 100, 98,  97,  96,  95,  94,  93],
        "high":  [101, 102, 103, 101, 99,  98,  97,  96,  95,  94],
        "low":   [99,  100, 101, 98,  97,  96,  95,  94,  93,  92],
        "close": [100, 101, 102, 99,  98,  97,  96,  95,  94,  93],
    }, index=dates)

    # Entry at index 0 (Long)
    signals = pd.DataFrame({"signal": [0] * len(data)}, index=data.index)
    signals.iloc[0, 0] = 1 # Long entry
    
    # Test SL: 2% (entry 100 -> SL 98)
    # Price hits 98 (low) at index 3
    metrics_sl = calc.calculate_all(data, signals, use_sl_tp=True, sl_pct=2.0, tp_pct=10.0)
    assert metrics_sl["trade_count"] == 1
    # entry 100, SL at 98.
    assert metrics_sl["total_return"] == -0.02
    
    # Test TP: 2% (entry 100 -> TP 102)
    # Price hits 102 (high) at index 1 (high is 102)
    metrics_tp = calc.calculate_all(data, signals, use_sl_tp=True, sl_pct=10.0, tp_pct=2.0)
    assert metrics_tp["trade_count"] == 1
    # entry 100, TP at 102.
    assert metrics_tp["total_return"] == 0.02

def test_calculate_batch_fast(sample_ohlcv):
    """Test parallel batch calculation functions."""
    import numpy as np
    from monte_neo.metrics.calculator import MetricsCalculator
    
    calc = MetricsCalculator()
    
    # Setup data
    ohlc = sample_ohlcv[["open", "high", "low", "close"]].values.astype(np.float32)
    prices = ohlc[:, 3]
    highs = ohlc[:, 1]
    lows = ohlc[:, 2]
    
    # 3 identical scenarios
    signals_matrix = np.zeros((3, len(ohlc)), dtype=np.float32)
    signals_matrix[:, 0] = 1 # Long entry for all
    
    # Test single-price batch (same OHLC for all)
    results = calc.calculate_batch_fast(
        prices,
        highs,
        lows,
        signals_matrix,
        use_sl_tp=True,
        sl_pct=2.0,
        tp_pct=4.0
    )
    
    assert len(results) == 3
    for res in results:
        assert res[3] == 1 # n_trades is at index 3
        
    # Test multi-price batch (different OHLC for each)
    price_matrix = np.stack([prices] * 3) # (3, L)
    high_matrix = np.stack([highs] * 3)
    low_matrix = np.stack([lows] * 3)
    
    results_multi = calc.calculate_batch_multi_price_fast(
        price_matrix,
        high_matrix,
        low_matrix,
        signals_matrix,
        use_sl_tp=True,
        sl_pct=2.0,
        tp_pct=4.0
    )
    
    assert len(results_multi) == 3
    for res in results_multi:
        assert res[3] == 1
