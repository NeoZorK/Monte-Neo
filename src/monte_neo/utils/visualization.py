"""Visualization utilities for backtest results.
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from typing import Any, List, Dict

def plot_equity_curves(results: List[Dict[str, Any]], title: str = "Monte Carlo Equity Curves"):
    """Plot equity curves for all scenarios."""
    plt.figure(figsize=(12, 6))
    
    # If results contain equity history, plot them. 
    # Currently our results only contain final metrics.
    # To plot equity curves, we need to return them from the engine.
    # For now, let's plot a distribution of final returns.
    
    returns = [res['metrics']['total_return'] for res in results]
    
    sns.histplot(returns, kde=True)
    plt.axvline(np.mean(returns), color='r', linestyle='--', label=f'Mean: {np.mean(returns):.2%}')
    plt.axvline(0, color='k', linestyle='-')
    plt.title(title)
    plt.xlabel("Total Return")
    plt.ylabel("Frequency")
    plt.legend()
    plt.grid(True, alpha=0.3)
    return plt

def plot_drawdown_dist(results: List[Dict[str, Any]], title: str = "Max Drawdown Distribution"):
    """Plot distribution of maximum drawdowns."""
    plt.figure(figsize=(10, 5))
    drawdowns = [res['metrics']['max_drawdown'] for res in results]
    
    sns.histplot(drawdowns, kde=True, color='orange')
    plt.axvline(np.mean(drawdowns), color='r', linestyle='--', label=f'Mean DD: {np.mean(drawdowns):.2%}')
    plt.title(title)
    plt.xlabel("Max Drawdown")
    plt.ylabel("Frequency")
    plt.legend()
    plt.grid(True, alpha=0.3)
    return plt

def plot_metrics_summary(results: List[Dict[str, Any]]):
    """Plot a summary table/heatmap of key metrics."""
    metrics_df = pd.DataFrame([res['metrics'] for res in results])
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    sns.boxplot(y=metrics_df['total_return'], ax=axes[0,0], color='skyblue')
    axes[0,0].set_title("Total Return")
    
    sns.boxplot(y=metrics_df['sharpe_ratio'], ax=axes[0,1], color='lightgreen')
    axes[0,1].set_title("Sharpe Ratio")
    
    sns.boxplot(y=metrics_df['win_rate'], ax=axes[1,0], color='salmon')
    axes[1,0].set_title("Win Rate")
    
    sns.boxplot(y=metrics_df['max_drawdown'], ax=axes[1,1], color='orange')
    axes[1,1].set_title("Max Drawdown")
    
    plt.tight_layout()
    return fig
