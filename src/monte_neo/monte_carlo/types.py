"""Types for Monte Carlo simulations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


@dataclass
class MCConfig:
    """Monte Carlo configuration."""

    iterations: int = 10000
    use_shuffling: bool = True
    use_noise: bool = True
    use_sensitivity: bool = True
    use_walk_forward: bool = True
    use_block_bootstrap: bool = True
    use_sequential: bool = False
    sensitivity_range: float = 0.10  # ±10%
    walk_forward_splits: int = 5
    n_workers: int | None = None
    random_seed: int | None = None

    # Risk Management
    use_sl_tp: bool = False
    sl_pct: float = 0.0
    tp_pct: float = 0.0

    # Validation
    pass_threshold: float = 0.95  # 95% threshold by default


@dataclass
class MCStepResult:
    """Result of a single Monte Carlo step."""

    method_name: str
    passed: bool
    pass_rate: float
    metrics_summary: dict
    advice: str


@dataclass
class MCResult:
    """Monte Carlo simulation result."""

    passed: bool
    pass_rate: float
    iterations_run: int
    elapsed_time: float
    metrics_summary: dict = field(default_factory=dict)
    detailed_results: list = field(default_factory=list)
    step_results: list[MCStepResult] = field(default_factory=list)
