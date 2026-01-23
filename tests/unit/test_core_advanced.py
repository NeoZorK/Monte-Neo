"""Unit tests for optimizer and validator."""

from monte_neo.core.optimizer import ParameterOptimizer
from monte_neo.core.validator import OverfitValidator
from monte_neo.indicators.technical import SMAIndicator
from monte_neo.metrics.calculator import MetricsCalculator


def test_parameter_optimizer(sample_ohlcv):
    optimizer = ParameterOptimizer(method="random", max_iterations=20, random_seed=42)
    indicator = SMAIndicator()
    metrics_calc = MetricsCalculator()

    ranges = {
        "fast_period": (5, 15),
        "slow_period": (20, 40)
    }

    result = optimizer.optimize(
        indicator, ranges, sample_ohlcv, metrics_calc, objective="profit_factor"
    )

    assert result.best_score >= 0
    assert len(result.best_params) == 2
    assert "fast_period" in result.best_params

def test_overfit_validator(sample_ohlcv):
    validator = OverfitValidator(min_trades=1) # Small min trades for test
    indicator = SMAIndicator()
    metrics_calc = MetricsCalculator()

    # Needs some trades to pass
    target_metrics = {"profit_factor": 0.5}

    result = validator.validate(
        indicator, sample_ohlcv, metrics_calc, target_metrics
    )

    assert hasattr(result, "passed")
    assert isinstance(result.overall_score, float)
    assert len(result.in_sample_metrics) > 0
