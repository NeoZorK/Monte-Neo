"""Integration tests for full workflow."""

import pandas as pd

from monte_neo.core.generator import GeneratorConfig, IndicatorGenerator
from monte_neo.data.storage import ParquetStorage
from monte_neo.metrics.calculator import MetricsCalculator


def test_full_generation_workflow(tmp_path, sample_ohlcv):
    # Setup storage
    storage = ParquetStorage(tmp_path)
    storage.save(sample_ohlcv, "BTCUSDT", "1h")

    # Configure generator
    config = GeneratorConfig(
        max_iterations=10,  # Very few for testing
        target_metrics={"profit_factor": 1.1, "sharpe_ratio": 0.5},
        indicator_types=["sma", "rsi"],
        mc_iterations=5,
        use_mc_shuffling=True,
        use_mc_noise=True,
        early_stopping=False,
    )

    generator = IndicatorGenerator(config)

    # Run generation
    data = storage.load("BTCUSDT", "1h")
    result = generator.generate(data)

    # Verify result structure
    assert result.elapsed_time > 0
    assert result.iterations_tried > 0
    assert isinstance(result.success, bool)

    if result.indicator:
        assert len(result.final_metrics) > 0
        assert "profit_factor" in result.final_metrics
        # Test that we can re-generate signals from found indicator
        signals = result.indicator.generate_signals(data)
        assert len(signals) == len(data)


def test_metrics_consistency(sample_ohlcv):
    """Verify that multiple calculations yield same results."""
    calc = MetricsCalculator()

    # Mock signals
    signals = pd.DataFrame(index=sample_ohlcv.index)
    signals["signal"] = 0
    signals.iloc[10] = 1
    signals.iloc[20] = -1

    m1 = calc.calculate_all(sample_ohlcv, signals)
    m2 = calc.calculate_all(sample_ohlcv, signals)

    assert m1["profit_factor"] == m2["profit_factor"]
    assert m1["sharpe_ratio"] == m2["sharpe_ratio"]
    assert m1["max_drawdown"] == m2["max_drawdown"]


def test_monte_carlo_engine_robustness(sample_ohlcv):
    from monte_neo.indicators.technical import SMAIndicator
    from monte_neo.monte_carlo.engine import MCConfig, MonteCarloEngine

    indicator = SMAIndicator()
    config = MCConfig(iterations=10)
    engine = MonteCarloEngine(config=config)
    metrics_calc = MetricsCalculator()
    target_metrics = {"profit_factor": 1.0}

    # Run MC on the data
    result = engine.run(sample_ohlcv, indicator, metrics_calc, target_metrics)

    assert hasattr(result, "passed")
    assert result.pass_rate >= 0
    assert len(result.detailed_results) > 0
