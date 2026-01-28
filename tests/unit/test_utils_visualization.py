import pytest
import matplotlib.pyplot as plt
import pandas as pd
from unittest.mock import patch
from monte_neo.utils.visualization import (
    plot_equity_curves, 
    plot_drawdown_dist, 
    plot_metrics_summary,
    plot_stress_test_summary
)

@pytest.fixture
def mock_results():
    return [
        {
            "metrics": {
                "total_return": 0.1,
                "max_drawdown": 0.05,
                "sharpe_ratio": 1.5,
                "win_rate": 0.6
            }
        },
        {
            "metrics": {
                "total_return": 0.2,
                "max_drawdown": 0.08,
                "sharpe_ratio": 2.0,
                "win_rate": 0.65
            }
        }
    ]

@patch("matplotlib.pyplot.show")
def test_plot_equity_curves(mock_show, mock_results):
    fig = plot_equity_curves(mock_results)
    assert fig is not None
    plt.close()

@patch("matplotlib.pyplot.show")
def test_plot_drawdown_dist(mock_show, mock_results):
    fig = plot_drawdown_dist(mock_results)
    assert fig is not None
    plt.close()

@patch("matplotlib.pyplot.show")
def test_plot_metrics_summary(mock_show, mock_results):
    fig = plot_metrics_summary(mock_results)
    assert fig is not None
    plt.close()

@patch("matplotlib.pyplot.show")
def test_plot_stress_test_summary(mock_show):
    stress_data = {
        "black_swan": {"total_return": -0.5},
        "sensitivity": {"std_return_variation": 0.02},
        "breaking_point": {"breaking_point_bps": 150}
    }
    fig = plot_stress_test_summary(stress_data)
    assert fig is not None
    plt.close()
