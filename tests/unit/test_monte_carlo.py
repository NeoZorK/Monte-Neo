"""Unit tests for Monte Carlo engine."""

from monte_neo.indicators.technical import SMAIndicator
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.engine import MCConfig, MonteCarloEngine


def test_mc_engine_init():
    config = MCConfig(iterations=100)
    engine = MonteCarloEngine(config)
    assert engine.config.iterations == 100


def test_mc_run(sample_ohlcv):
    config = MCConfig(
        iterations=10,
        use_shuffling=True,
        use_noise=False,
        use_sensitivity=False,
        use_walk_forward=False,
    )
    engine = MonteCarloEngine(config)
    indicator = SMAIndicator()
    metrics_calc = MetricsCalculator()

    target_metrics = {
        "profit_factor": 0.5,  # Low target to ensure pass
    }

    result = engine.run(sample_ohlcv, indicator, metrics_calc, target_metrics)

    assert result.iterations_run > 0
    assert "profit_factor" in result.metrics_summary
