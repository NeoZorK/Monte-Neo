import numpy as np
import pandas as pd
import pytest

from monte_neo.core.portfolio.manager import PortfolioAsset, PortfolioManager
from monte_neo.core.portfolio.risk import (
    calculate_kelly_fraction,
    calculate_risk_parity_weights,
    calculate_volatility_adjusted_size,
)


def test_portfolio_asset_init():
    asset = PortfolioAsset(id="test", indicator_path="path", symbol="BTC")
    assert asset.id == "test"
    assert asset.symbol == "BTC"
    assert asset.weight == 1.0
    assert asset.active is True

def test_portfolio_manager_add_asset():
    pm = PortfolioManager(initial_capital=5000)
    asset = PortfolioAsset(id="test", indicator_path="path", symbol="BTC")
    pm.add_asset(asset)
    assert len(pm.assets) == 1
    assert pm.initial_capital == 5000

def test_calculate_correlations():
    pm = PortfolioManager()
    returns = {
        "A": pd.Series([0.01, 0.02, -0.01]),
        "B": pd.Series([-0.01, -0.02, 0.01])
    }
    corr = pm.calculate_correlations(returns)
    assert corr.loc["A", "B"] < 0
    assert pm.correlation_matrix is not None

def test_cluster_assets():
    pm = PortfolioManager()
    returns = {
        "A": pd.Series([0.01, 0.02, 0.01, 0.02]),
        "B": pd.Series([0.011, 0.021, 0.011, 0.021]), # Highly correlated with A
        "C": pd.Series([-0.01, 0.05, -0.02, 0.01])   # Different
    }
    clusters = pm.cluster_assets(returns)
    assert len(clusters) > 0
    # Single asset case
    assert pm.cluster_assets({"A": returns["A"]}) == {0: ["A"]}

def test_optimize_weights():
    pm = PortfolioManager()
    a1 = PortfolioAsset(id="A", indicator_path="p", symbol="S1")
    a2 = PortfolioAsset(id="B", indicator_path="p", symbol="S2")
    pm.add_asset(a1)
    pm.add_asset(a2)
    
    # Equal
    weights = pm.optimize_weights(method="equal")
    assert weights["A"] == 0.5
    assert weights["B"] == 0.5
    
    # Risk Parity
    vols = [0.1, 0.2]
    weights = pm.optimize_weights(method="risk_parity", volatilities=vols)
    assert weights["A"] > weights["B"] # Lower vol gets higher weight
    
    # Kelly
    weights = pm.optimize_weights(method="kelly")
    assert "A" in weights

def test_get_combined_equity():
    pm = PortfolioManager()
    e1 = np.array([100, 105, 110])
    e2 = np.array([100, 95, 90])
    pm.add_asset(PortfolioAsset(id="A", indicator_path="p", symbol="S1", equity_curve=e1, weight=0.6))
    pm.add_asset(PortfolioAsset(id="B", indicator_path="p", symbol="S2", equity_curve=e2, weight=0.4))
    
    combined = pm.get_combined_equity()
    assert len(combined) == 3
    assert combined[0] == 100 * 0.6 + 100 * 0.4
    assert combined[1] == 105 * 0.6 + 95 * 0.4

def test_portfolio_monte_carlo():
    pm = PortfolioManager()
    e = np.array([100, 102, 101, 105, 104, 110])
    pm.add_asset(PortfolioAsset(id="A", indicator_path="p", symbol="S1", equity_curve=e))
    
    res = pm.run_portfolio_monte_carlo(iterations=10)
    assert "avg_return" in res
    assert "max_drawdown_95th" in res

def test_auto_rebalance():
    pm = PortfolioManager()
    e1 = np.array([100, 101, 102, 103]) # Low vol
    e2 = np.array([100, 110, 90, 120])  # High vol
    pm.add_asset(PortfolioAsset(id="A", indicator_path="p", symbol="S1", equity_curve=e1))
    pm.add_asset(PortfolioAsset(id="B", indicator_path="p", symbol="S2", equity_curve=e2))
    
    weights = pm.auto_rebalance(method="risk_parity")
    assert weights["A"] > weights["B"]

def test_risk_functions():
    # Kelly
    assert calculate_kelly_fraction(0.6, 2.0) > 0
    assert calculate_kelly_fraction(0.4, 1.0) == 0
    assert calculate_kelly_fraction(0.6, -1) == 0
    
    # Vol adjusted size
    assert calculate_volatility_adjusted_size(0.2, 0.1, 1000) == 500
    assert calculate_volatility_adjusted_size(0, 0.1, 1000) == 0
    
    # Risk parity weights
    vols = [0.1, 0.2, 0.4]
    w = calculate_risk_parity_weights(vols)
    assert len(w) == 3
    assert sum(w) == pytest.approx(1.0)
    assert w[0] > w[1] > w[2]
    assert calculate_risk_parity_weights([]) == []
    assert calculate_risk_parity_weights([0, 0]) == [0.5, 0.5]
