"""Portfolio management module.

Handles multiple indicators, risk allocation, and correlation analysis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

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
    equity_curve: Optional[np.ndarray] = None

class PortfolioManager:
    """Manages a collection of indicators as a single trading portfolio."""

    def __init__(self, initial_capital: float = 10000.0):
        self.assets: List[PortfolioAsset] = []
        self.initial_capital = initial_capital
        self.correlation_matrix: Optional[pd.DataFrame] = None

    def add_asset(self, asset: PortfolioAsset):
        """Add an asset to the portfolio."""
        self.assets.append(asset)
        logger.info(f"Added asset {asset.id} for {asset.symbol} to portfolio")

    def calculate_correlations(self, returns_dict: Dict[str, pd.Series]) -> pd.DataFrame:
        """Calculate correlation matrix between assets based on their returns."""
        df = pd.DataFrame(returns_dict)
        self.correlation_matrix = df.corr()
        return self.correlation_matrix

    def optimize_weights(self, method: str = "risk_parity") -> Dict[str, float]:
        """Optimize asset weights based on selected method."""
        if not self.assets:
            return {}
        
        if method == "equal":
            weight = 1.0 / len(self.assets)
            for asset in self.assets:
                asset.weight = weight
        
        # More advanced methods (Risk Parity, Kelly) to be implemented
        return {a.id: a.weight for a in self.assets}

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get high-level portfolio statistics."""
        return {
            "total_assets": len(self.assets),
            "active_assets": sum(1 for a in self.assets if a.active),
            "initial_capital": self.initial_capital,
            "weights": {a.id: a.weight for a in self.assets}
        }
