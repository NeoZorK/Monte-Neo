import pytest
import numpy as np
from monte_neo.metrics.drawdown import DrawdownMetric

@pytest.fixture
def dd_calc():
    return DrawdownMetric()

def test_calculate_max_drawdown(dd_calc):
    # Equity: 100 -> 120 -> 90 -> 110 -> 150
    # Peaks: 100, 120, 120, 120, 150
    # DDs: 0, 0, (120-90)/120=0.25, (120-110)/120=0.083, 0
    equity = [100.0, 120.0, 90.0, 110.0, 150.0]
    assert dd_calc.calculate_max(equity) == pytest.approx(0.25)

def test_calculate_avg_drawdown(dd_calc):
    equity = [100.0, 120.0, 90.0, 110.0, 150.0]
    # Non-zero DDs: 0.25, 0.08333...
    avg = (0.25 + 0.0833333333) / 2
    assert dd_calc.calculate_avg(equity) == pytest.approx(avg)

def test_calculate_drawdown_duration(dd_calc):
    # 100 (peak), 90 (dd), 80 (dd), 110 (peak), 100 (dd), 120 (peak)
    equity = [100, 90, 80, 110, 100, 120]
    # DD periods: [F, T, T, F, T, F]
    # Durations: 0, 1, 2, 0, 1, 0 -> Max 2
    assert dd_calc.calculate_duration(equity) == 2

def test_get_drawdown_curve(dd_calc):
    equity = [100, 120, 90]
    curve = dd_calc.get_drawdown_curve(equity)
    assert len(curve) == 3
    assert curve[2] == pytest.approx(0.25)

def test_empty_equity(dd_calc):
    assert dd_calc.calculate_max([]) == 0.0
    assert dd_calc.calculate_avg([]) == 0.0
    assert dd_calc.calculate_duration([]) == 0
