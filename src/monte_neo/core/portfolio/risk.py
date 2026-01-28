"""Risk management module for portfolio optimization."""

from __future__ import annotations


def calculate_kelly_fraction(win_rate: float, win_loss_ratio: float) -> float:
    """
    Calculate Kelly Criterion fraction.
    
    Formula: K = W - (1 - W) / R
    W = Win probability
    R = Win/Loss ratio (Avg Win / Avg Loss)
    """
    if win_loss_ratio <= 0:
        return 0.0
    
    kelly = win_rate - (1.0 - win_rate) / win_loss_ratio
    return max(0.0, kelly)

def calculate_volatility_adjusted_size(
    volatility: float,
    target_volatility: float = 0.15,
    equity: float = 10000.0
) -> float:
    """
    Calculate position size based on target volatility (Volatility Targeting).
    """
    if volatility <= 0:
        return 0.0
    
    # Simple Volatility Targeting: Size = (Target Vol / Current Vol) * Equity
    size = (target_volatility / volatility) * equity
    return size

def calculate_risk_parity_weights(volatilities: list[float]) -> list[float]:
    """
    Calculate weights such that each asset contributes equal risk (inverse of volatility).
    """
    if not volatilities:
        return []
    
    inv_vols = [1.0 / v if v > 0 else 0 for v in volatilities]
    total_inv_vol = sum(inv_vols)
    
    if total_inv_vol == 0:
        return [1.0 / len(volatilities)] * len(volatilities)
    
    return [iv / total_inv_vol for iv in inv_vols]
