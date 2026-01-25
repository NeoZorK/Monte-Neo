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
