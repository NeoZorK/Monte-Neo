"""Unit tests for Generator."""

from monte_neo.core.generator import GeneratorConfig, IndicatorGenerator


def test_generator_config():
    config = GeneratorConfig(max_iterations=500)
    gen = IndicatorGenerator(config)
    assert gen.config.max_iterations == 500


def test_generator_random_indicator():
    gen = IndicatorGenerator()
    indicator = gen._generate_random_indicator()
    assert indicator is not None
    assert hasattr(indicator, "calculate")
