import numpy as np
import pandas as pd
import pytest

from monte_neo.indicators.sma import SMAIndicator
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.cscv import CSCVAnalyzer


@pytest.fixture
def sample_data():
    dates = pd.date_range("2023-01-01", periods=100)
    data = pd.DataFrame({
        "open": np.linspace(100, 110, 100),
        "high": np.linspace(102, 112, 100),
        "low": np.linspace(98, 108, 100),
        "close": np.linspace(100, 110, 100) + np.random.randn(100),
        "volume": [1000] * 100
    }, index=dates)
    return data

def test_cscv_analyze(sample_data):
    analyzer = CSCVAnalyzer()
    from monte_neo.indicators.base import IndicatorConfig
    config = IndicatorConfig(name="SMA", parameters={"fast_period": 5, "slow_period": 10})
    indicator = SMAIndicator(config=config)
    metrics_calc = MetricsCalculator()
    
    res = analyzer.analyze(indicator, sample_data, metrics_calc, n_segments=5)
    
    assert "pbo" in res
    assert "is_robust" in res
    assert len(res["segment_scores"]) == 5

def test_cscv_insufficient_data():
    analyzer = CSCVAnalyzer()
    data = pd.DataFrame({"a": [1]})
    res = analyzer.analyze(None, data, None, n_segments=10)
    assert "error" in res
