import numpy as np
import pandas as pd
import pytest

from monte_neo.core.validator import OverfitValidator
from monte_neo.indicators.base import IndicatorConfig
from monte_neo.indicators.sma import SMAIndicator
from monte_neo.metrics.calculator import MetricsCalculator


@pytest.fixture
def sample_data():
    dates = pd.date_range("2023-01-01", periods=200)
    data = pd.DataFrame({
        "open": np.linspace(100, 110, 200),
        "high": np.linspace(102, 112, 200),
        "low": np.linspace(98, 108, 200),
        "close": np.linspace(100, 110, 200) + np.random.randn(200),
        "volume": [1000] * 200
    }, index=dates)
    return data

@pytest.fixture
def indicator():
    config = IndicatorConfig(name="SMA", parameters={"fast_period": 5, "slow_period": 10})
    return SMAIndicator(config=config)

def test_validator_init():
    v = OverfitValidator(min_trades=50, min_oos_ratio=0.5)
    assert v.min_trades == 50
    assert v.min_oos_ratio == 0.5

def test_check_non_repainting(indicator, sample_data):
    v = OverfitValidator()
    assert v.check_non_repainting(indicator, sample_data) is True

def test_validate_full(indicator, sample_data):
    v = OverfitValidator(min_trades=5)
    metrics_calc = MetricsCalculator()
    target_metrics = {"sharpe_ratio": 0.5}
    
    res = v.validate(indicator, sample_data, metrics_calc, target_metrics)
    assert hasattr(res, "passed")
    assert hasattr(res, "overall_score")
    assert isinstance(res.warnings, list)

def test_quick_check(indicator, sample_data):
    v = OverfitValidator(min_trades=5)
    metrics_calc = MetricsCalculator()
    # SMA crossover should pass basic checks on randomish data if min_trades is low
    res = v.quick_check(indicator, sample_data, metrics_calc)
    assert isinstance(res, bool)
