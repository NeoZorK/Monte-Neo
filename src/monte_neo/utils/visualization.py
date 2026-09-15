"""Visualization utilities for backtest results.
"""

from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def plot_equity_curves(results: list[dict[str, Any]], title: str = "Monte Carlo Equity Curves"):
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

def plot_drawdown_dist(results: list[dict[str, Any]], title: str = "Max Drawdown Distribution"):
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

def plot_metrics_summary(results: list[dict[str, Any]]):
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

def plot_stress_test_summary(stress_results: dict[str, Any]):
    """Plot a summary of stress test results."""
    plt.figure(figsize=(10, 6))
    
    names = []
    values = []
    
    # 1. Black Swan Impact
    bs = stress_results.get("black_swan", {})
    if bs:
        names.append("Black Swan Ret")
        values.append(bs.get("total_return", 0))
        
    # 2. Sensitivity
    sens = stress_results.get("sensitivity", {})
    if sens:
        names.append("Sens. Std Var")
        values.append(sens.get("std_return_variation", 0))
        
    # 3. Breaking Point
    bp = stress_results.get("breaking_point", {})
    if bp:
        bp_val = bp.get("breaking_point_bps", 0)
        if isinstance(bp_val, str) and ">" in bp_val:
            bp_val = float(bp_val.replace(">", "").strip())
        names.append("Break Pt (bps)/100") # Scaled for plotting
        values.append(float(bp_val) / 100.0)
        
    plt.bar(names, values, color=['red', 'blue', 'green'])
    plt.axhline(0, color='black', linewidth=1)
    plt.title("Deep Stress Test Summary")
    plt.ylabel("Metric Value")
    plt.grid(True, alpha=0.3)
    
    return plt

def plot_sensitivity_heatmap(sensitivity_results: dict[str, Any]):
    """Plot a heatmap of parameter sensitivity."""
    grid = sensitivity_results.get("grid")
    if not grid or not grid.get("matrix"):
        return None
        
    plt.figure(figsize=(10, 8))
    
    matrix = np.array(grid["matrix"])
    p1_vals = [f"{v:.2f}" for v in grid["p1_values"]]
    p2_vals = [f"{v:.2f}" for v in grid["p2_values"]]
    
    sns.heatmap(matrix, annot=True, fmt=".2%", xticklabels=p2_vals, yticklabels=p1_vals, cmap="RdYlGn")
    plt.title(f"Sensitivity: {grid['p1_name']} vs {grid['p2_name']}")
    plt.xlabel(grid["p2_name"])
    plt.ylabel(grid["p1_name"])
    
    return plt
