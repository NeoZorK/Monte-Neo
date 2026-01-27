from __future__ import annotations

import time
import pandas as pd
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from monte_neo.core.generator import IndicatorGenerator

# Parameter search spaces for each indicator type
PARAM_SPACES = {
    "sma": {
        "fast_period": (5, 50),
        "slow_period": (20, 200),
    },
    "rsi": {
        "period": (5, 30),
        "overbought": (65, 85),
        "oversold": (15, 35),
    },
    "macd": {
        "fast": (8, 20),
        "slow": (20, 40),
        "signal": (5, 15),
    },
    "dynamic": {},
}


def estimate_time(generator: Any, data: pd.DataFrame) -> float:
    """Estimate generation time in minutes.

    Args:
        generator: IndicatorGenerator instance (typed as Any to avoid circular import)
        data: Sample data.

    Returns:
        Estimated time in minutes.
    """
    # Run small sample
    sample_iterations = 10
    start = time.time()

    for _ in range(sample_iterations):
        indicator = generator._generate_random_indicator()
        signals = indicator.generate_signals(data)
        _ = generator.metrics_calc.calculate_all(data, signals)

    elapsed = time.time() - start
    time_per_iter = elapsed / sample_iterations

    # Account for MC validation (~10x slower)
    mc_factor = (
        10
        if any(
            [
                generator.config.use_mc_shuffling,
                generator.config.use_mc_noise,
            ]
        )
        else 2
    )

    total_seconds = time_per_iter * generator.config.max_iterations * mc_factor
    return total_seconds / 60
