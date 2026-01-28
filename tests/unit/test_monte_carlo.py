"""Unit tests for Monte Carlo engine."""

from monte_neo.indicators.technical import SMAIndicator
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.engine import MCConfig, MonteCarloEngine


def test_mc_engine_init():
    config = MCConfig(iterations=100, pass_threshold=0.85)
    engine = MonteCarloEngine(config)
    assert engine.config.iterations == 100
    assert engine.config.pass_threshold == 0.85


def test_mc_run_sequential(sample_ohlcv):
    """Test sequential MC execution."""
    config = MCConfig(
        iterations=5,
        use_shuffling=True,
        use_noise=True,
        use_sequential=True,
        pass_threshold=0.0, # 0.0 threshold should always pass if it runs
    )
    engine = MonteCarloEngine(config)
    indicator = SMAIndicator()
    metrics_calc = MetricsCalculator()
    target_metrics = {"profit_factor": 0.1}

    result = engine.run(sample_ohlcv, indicator, metrics_calc, target_metrics, interactive=False)

    assert result.passed is True
    assert len(result.step_results) > 0
    assert result.step_results[0].method_name in ["Walk-Forward Analysis", "Block Bootstrap", "Return Shuffling", "Noise Injection"]


def test_mc_run(sample_ohlcv):
    config = MCConfig(
        iterations=10,
        use_shuffling=True,
        use_noise=False,
        use_sensitivity=False,
        use_walk_forward=False,
        use_sequential=True, # Use sequential to avoid pickling issues in tests
    )
    engine = MonteCarloEngine(config)
    indicator = SMAIndicator()
    metrics_calc = MetricsCalculator()

    target_metrics = {
        "profit_factor": 0.5,  # Low target to ensure pass
    }

    result = engine.run(sample_ohlcv, indicator, metrics_calc, target_metrics, interactive=False)

    assert result.iterations_run > 0
    assert "profit_factor" in result.metrics_summary
