"""Generator configuration module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from monte_neo.indicators.base import BaseIndicator


@dataclass
class GeneratorConfig:
    """Generator configuration."""

    max_iterations: int = 100000
    target_metrics: dict[str, float] = field(default_factory=dict)
    indicator_types: list[str] = field(
        default_factory=lambda: ["sma", "rsi", "macd", "dynamic"]
    )
    mc_iterations: int = 1000
    use_mc_shuffling: bool = True
    use_mc_noise: bool = True
    use_mc_sensitivity: bool = True
    use_mc_walk_forward: bool = True
    use_mc_block_bootstrap: bool = True
    early_stopping: bool = True
    min_trades: int = 30
    population_size: int = 50
    generations: int = 20
    mutation_rate: float = 0.3
    crossover_rate: float = 0.7


@dataclass
class GeneratorResult:
    """Generator result."""

    success: bool
    indicator: BaseIndicator | None
    parameters: dict
    final_metrics: dict
    mc_pass_rate: float
    iterations_tried: int
    elapsed_time: float
    candidates_found: int
