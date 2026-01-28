"""Portfolio management module.

Handles multiple indicators, risk allocation, and correlation analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class PortfolioAsset:
    """Represents an indicator/strategy in the portfolio."""
    id: str
    indicator_path: str
    symbol: str
    weight: float = 1.0
    active: bool = True
    equity_curve: np.ndarray | None = None

class PortfolioManager:
    """Manages a collection of indicators as a single trading portfolio."""

    def __init__(self, initial_capital: float = 10000.0):
        self.assets: list[PortfolioAsset] = []
        self.initial_capital = initial_capital
        self.correlation_matrix: pd.DataFrame | None = None

    def add_asset(self, asset: PortfolioAsset):
        """Add an asset to the portfolio."""
        self.assets.append(asset)
        logger.info(f"Added asset {asset.id} for {asset.symbol} to portfolio")

    def calculate_correlations(self, returns_dict: dict[str, pd.Series]) -> pd.DataFrame:
        """Calculate correlation matrix between assets based on their returns."""
        df = pd.DataFrame(returns_dict)
        self.correlation_matrix = df.corr()
        return self.correlation_matrix

    def cluster_assets(self, returns_dict: dict[str, pd.Series]) -> dict[int, list[str]]:
        """Cluster assets based on correlation to find redundant strategies."""
        try:
            from scipy.cluster.hierarchy import fcluster, linkage
            from scipy.spatial.distance import squareform
        except ImportError:
            logger.warning("scipy not installed, skipping clustering")
            return {0: list(returns_dict.keys())}
            
        if len(returns_dict) < 2:
            return {0: list(returns_dict.keys())}
            
        corr = self.calculate_correlations(returns_dict)
        # Convert correlation to distance (1 - corr)
        dist = 1 - corr.fillna(0)
        
        # Ensure symmetry and 0 diagonal for squareform
        dist = (dist + dist.T) / 2
        np.fill_diagonal(dist.values, 0)
        
        # Hierarchical clustering
        try:
            from scipy.cluster.hierarchy import fcluster, linkage
            from scipy.spatial.distance import squareform
            
            link = linkage(squareform(dist), method='ward')
            clusters = fcluster(link, t=0.5, criterion='distance')
            
            cluster_map = {}
            for asset_id, cluster_id in zip(corr.index, clusters):
                if cluster_id not in cluster_map:
                    cluster_map[int(cluster_id)] = []
                cluster_map[int(cluster_id)].append(asset_id)
                
            return cluster_map
        except Exception as e:
            logger.error(f"Clustering failed: {e}")
            return {0: list(returns_dict.keys())}

    def optimize_weights(self, method: str = "risk_parity", volatilities: list[float] | None = None) -> dict[str, float]:
        """Optimize asset weights based on selected method."""
        if not self.assets:
            return {}
        
        if method == "equal":
            weight = 1.0 / len(self.assets)
            for asset in self.assets:
                asset.weight = weight
        
        elif method == "risk_parity" and volatilities:
            from monte_neo.core.portfolio.risk import calculate_risk_parity_weights
            weights = calculate_risk_parity_weights(volatilities)
            for asset, weight in zip(self.assets, weights):
                asset.weight = weight
                
        elif method == "kelly":
            # Advanced Kelly Criterion for multiple assets
            # f* = (p/a - q/b) where p is win probability, q is loss probability, a is fractional loss, b is fractional gain
            for asset in self.assets:
                # Mock values for now, should be calculated from equity_curve
                win_rate = 0.55
                win_loss_ratio = 1.2
                kelly_f = win_rate - (1 - win_rate) / win_loss_ratio
                asset.weight = max(0, kelly_f * 0.5) # Half-Kelly for safety
        
        return {a.id: a.weight for a in self.assets}

    def run_portfolio_monte_carlo(self, iterations: int = 1000) -> dict[str, Any]:
        """Runs Monte Carlo simulation on the combined portfolio equity."""
        combined_equity = self.get_combined_equity()
        if len(combined_equity) == 0:
            return {}
            
        from monte_neo.monte_carlo.engine import MonteCarloEngine
        mc_engine = MonteCarloEngine()
        
        # We simulate variations of the combined returns
        returns = np.diff(combined_equity) / combined_equity[:-1]
        
        results = []
        for _ in range(iterations):
            # Shuffle returns to simulate different sequences
            shuffled_returns = np.random.permutation(returns)
            sim_equity = np.cumprod(1 + shuffled_returns)
            
            # Calculate drawdown
            peak = np.maximum.accumulate(sim_equity)
            drawdown = (peak - sim_equity) / peak
            results.append({
                "final_return": sim_equity[-1] - 1,
                "max_drawdown": np.max(drawdown)
            })
            
        return {
            "avg_return": np.mean([r["final_return"] for r in results]),
            "max_drawdown_95th": np.percentile([r["max_drawdown"] for r in results], 95),
            "var_95": np.percentile([r["final_return"] for r in results], 5)
        }

    def get_combined_equity(self) -> np.ndarray:
        """Calculate the combined equity curve of the portfolio."""
        if not self.assets:
            return np.array([])
            
        active_assets = [a for a in self.assets if a.active and a.equity_curve is not None]
        if not active_assets:
            return np.array([])
            
        # Sum weighted equity curves
        # Assuming all curves are same length for simplicity
        min_len = min(len(a.equity_curve) for a in active_assets)
        combined = np.zeros(min_len)
        
        for asset in active_assets:
            combined += asset.equity_curve[:min_len] * asset.weight
            
        return combined

    def get_portfolio_summary(self) -> dict[str, Any]:
        """Get high-level portfolio statistics."""
        summary = {
            "total_assets": len(self.assets),
            "active_assets": sum(1 for a in self.assets if a.active),
            "initial_capital": self.initial_capital,
            "weights": {a.id: a.weight for a in self.assets},
            "clusters": {}
        }
        
        # Add clustering info if we have enough assets
        if len(self.assets) >= 2:
            returns = {a.id: pd.Series(a.equity_curve).pct_change().dropna()
                       for a in self.assets if a.equity_curve is not None}
            if returns:
                summary["clusters"] = self.cluster_assets(returns)
                
        return summary

    def auto_rebalance(self, method: str = "risk_parity") -> dict[str, float]:
        """Automatically rebalance the portfolio based on latest metrics."""
        volatilities = []
        for asset in self.assets:
            if asset.equity_curve is not None:
                returns = pd.Series(asset.equity_curve).pct_change().dropna()
                volatilities.append(returns.std())
            else:
                volatilities.append(1.0) # Default
                
        return self.optimize_weights(method=method, volatilities=volatilities)
