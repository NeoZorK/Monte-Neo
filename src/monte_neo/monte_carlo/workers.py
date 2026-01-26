"""Monte Carlo workers.

Independent worker functions for parallel execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator
    from monte_neo.metrics.calculator import MetricsCalculator

# Global variable for shared memory in workers
SHARED_SCENARIOS: list[pd.DataFrame] | None = None
SHARED_DATA: pd.DataFrame | None = None


def _generate_signals_wrapper(args):
    """Helper for parallel signal generation."""
    indicator, df = args
    # Use shared data if available and df is None
    if df is None:
        if SHARED_DATA is None:
            # Fallback or error? For safety, return zeros or raise
            # But in parallel execution exceptions might be swallowed or messy.
            # We assume SHARED_DATA is set if df is None.
            return np.zeros(0, dtype=np.float32)
        df = SHARED_DATA

    sigs = indicator.generate_signals_fast(df)
    # Return numpy array to reduce IPC
    return np.asarray(sigs, dtype=np.float32)


def run_indicator_batch(args: tuple[list[BaseIndicator], pd.DataFrame | None]) -> list[np.ndarray]:
    """Run a batch of indicators on shared data."""
    indicators, df = args
    if df is None:
        if SHARED_DATA is None:
            return []
        df = SHARED_DATA

    results = []
    for ind in indicators:
        try:
            sigs = ind.generate_signals_fast(df)
            results.append(np.asarray(sigs, dtype=np.float32))
        except Exception:
            # Return zeros on failure to keep alignment
            results.append(np.zeros(len(df), dtype=np.float32))
    return results


def _generate_lazy_scenario_wrapper(args):
    """Helper for lazy scenario generation."""
    return run_block_bootstrap_scenario(*args)


def init_worker(scenarios: list[pd.DataFrame]) -> None:
    """Initialize worker with shared scenarios."""
    global SHARED_SCENARIOS
    SHARED_SCENARIOS = scenarios


def init_worker_data(data: pd.DataFrame) -> None:
    """Initialize worker with shared data."""
    global SHARED_DATA
    SHARED_DATA = data


def run_scenario_batch(
    scenarios: list[pd.DataFrame] | None,
    indicator: BaseIndicator,
    metrics_calc: MetricsCalculator,
    target_metrics: dict[str, float],
    indices: list[int] | None = None,
) -> list[tuple[bool, dict[str, float]]]:
    """Run a batch of scenarios in a single worker task.

    This reduces IPC overhead and allows reusing compiled indicator code.
    Can use explicitly passed scenarios OR shared scenarios via indices.
    """
    results = []
    required_metrics = list(target_metrics.keys())

    # Determine data source
    batch_data: list[pd.DataFrame]
    if scenarios is not None:
        batch_data = scenarios
    elif SHARED_SCENARIOS is not None and indices is not None:
        batch_data = [SHARED_SCENARIOS[i] for i in indices]
    else:
        # Fallback or error
        return []

    # Compile once per batch if needed
    if hasattr(indicator, "_compile_if_needed"):
        try:
            indicator._compile_if_needed()
        except Exception:
            pass

    for data in batch_data:
        try:
            signals = indicator.generate_signals_fast(data)
            metrics = metrics_calc.calculate_all(data, signals, required_metrics=required_metrics)

            # Inline check
            passed = True
            for metric_name, target_value in target_metrics.items():
                if metric_name not in metrics:
                    continue
                actual = metrics[metric_name]
                if metric_name in ["max_drawdown", "consecutive_losses"]:
                    if actual > target_value:
                        passed = False
                        break
                else:
                    if actual < target_value:
                        passed = False
                        break
            results.append((passed, metrics))
        except Exception:
            results.append((False, {}))

    return results


def run_single_scenario(
    scenario_data: pd.DataFrame,
    indicator: BaseIndicator,
    metrics_calc: MetricsCalculator,
    target_metrics: dict[str, float],
) -> tuple[bool, dict[str, float]]:
    """Helper for parallel execution (legacy/single mode)."""
    signals = indicator.generate_signals_fast(scenario_data)
    metrics = metrics_calc.calculate_all(
        scenario_data, signals, required_metrics=list(target_metrics.keys())
    )

    # Inline check_targets to avoid dependency on self
    passed = True
    for metric_name, target_value in target_metrics.items():
        if metric_name not in metrics:
            continue
        actual = metrics[metric_name]
        if metric_name in ["max_drawdown", "consecutive_losses"]:
            if actual > target_value:
                passed = False
                break
        else:
            if actual < target_value:
                passed = False
                break
    return passed, metrics


def run_block_bootstrap_scenario(
    indicator: BaseIndicator,
    seed: int,
    block_size: int | None = None
) -> Any | None:
    """Generate block bootstrap scenario on fly and run signal generation."""
    if SHARED_DATA is None:
        return None

    # Replicate block bootstrap logic for SINGLE scenario
    rng = np.random.default_rng(seed)
    n = len(SHARED_DATA)
    if block_size is None:
        block_size = max(1, int(np.sqrt(n)))

    n_blocks = n // block_size
    indices_range = np.arange(block_size)

    block_starts = rng.choice(n - block_size + 1, size=n_blocks, replace=True)
    full_indices = (block_starts[:, None] + indices_range).ravel()

    # Use iloc for speed (returns copy by default for fancy indexing)
    scenario_data = SHARED_DATA.iloc[full_indices]

    # Run indicator
    try:
        if hasattr(indicator, "_compile_if_needed"):
            indicator._compile_if_needed()

        signals = indicator.generate_signals_fast(scenario_data)

        # Extract signal array to reduce IPC
        signal_arr = np.asarray(signals, dtype=np.float32)

        # Calculate returns for GPU engine
        close_prices = scenario_data["close"].values
        returns = (close_prices[1:] / close_prices[:-1]) - 1

        # Extract OHLC for SL/TP calculations
        ohlc = scenario_data[["open", "high", "low", "close"]].values.astype(np.float32)

        return signal_arr, returns.astype(np.float32), ohlc
    except Exception:
        return None
