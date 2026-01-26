"""Utility functions for Monte Carlo simulations."""

from __future__ import annotations

import numpy as np


def summarize_metrics(results: list[dict]) -> dict:
    """Summarize metrics across all scenarios.

    Args:
        results: List of scenario results.

    Returns:
        Summary statistics.
    """
    if not results:
        return {}

    # Collect all metric values
    metric_values: dict[str, list] = {}
    for result in results:
        for name, value in result.get("metrics", {}).items():
            if name not in metric_values:
                metric_values[name] = []
            metric_values[name].append(value)

    # Calculate summary stats
    summary = {}
    for name, values in metric_values.items():
        arr = np.array(values, dtype=float)

        # Handle infinite values which cause warnings in std calculation
        # We replace inf with nan and use nan-aware functions
        is_inf = np.isinf(arr)
        if np.any(is_inf):
            arr[is_inf] = np.nan

        # Check if we have any valid data left
        if np.all(np.isnan(arr)):
            summary[name] = {
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "median": 0.0,
                "p5": 0.0,
                "p95": 0.0,
            }
            continue

        summary[name] = {
            "mean": float(np.nanmean(arr)),
            "std": float(np.nanstd(arr)),
            "min": float(np.nanmin(arr)),
            "max": float(np.nanmax(arr)),
            "median": float(np.nanmedian(arr)),
            "p5": float(np.nanpercentile(arr, 5)),
            "p95": float(np.nanpercentile(arr, 95)),
        }

    return summary
