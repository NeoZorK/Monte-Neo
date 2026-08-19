"""Scenario builder module.

Handles generation of various Monte Carlo scenarios.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from monte_neo.data.sampler import DataSampler
from monte_neo.monte_carlo.noise import NoiseInjector
from monte_neo.monte_carlo.sensitivity import SensitivityAnalyzer
from monte_neo.monte_carlo.shuffler import DataShuffler
from monte_neo.monte_carlo.walk_forward import WalkForwardAnalyzer

if TYPE_CHECKING:
    from monte_neo.monte_carlo.engine import MCConfig


class ScenarioBuilder:
    """Builder for Monte Carlo scenarios."""

    def __init__(self, config: MCConfig):
        """Initialize builder.

        Args:
            config: Monte Carlo configuration.
        """
        self.config = config
        self.shuffler = DataShuffler(self.config.random_seed)
        self.noise_injector = NoiseInjector(self.config.random_seed)
        self.sensitivity = SensitivityAnalyzer()
        self.walk_forward = WalkForwardAnalyzer()
        self.sampler = DataSampler(self.config.random_seed)

    def generate_shuffling(self, data: pd.DataFrame, iterations: int) -> list[pd.DataFrame]:
        """Generate shuffling scenarios."""
        scenarios = []
        scenarios.extend(self.shuffler.shuffle_returns(data, iterations // 2))
        scenarios.extend(self.shuffler.shuffle_blocks(data, iterations // 2))
        return scenarios

    def generate_noise(self, data: pd.DataFrame, iterations: int) -> list[pd.DataFrame]:
        """Generate noise scenarios."""
        return self.noise_injector.add_noise(data, iterations)

    def generate_walk_forward(self, data: pd.DataFrame) -> list[pd.DataFrame]:
        """Generate walk-forward scenarios."""
        return self.walk_forward.generate_scenarios(
            data,
            n_splits=self.config.walk_forward_splits,
        )

    def generate_block_bootstrap(self, data: pd.DataFrame, iterations: int) -> list[pd.DataFrame]:
        """Generate block bootstrap scenarios."""
        return self.sampler.block_bootstrap(data, n_samples=iterations)

    def generate(self, data: pd.DataFrame) -> list[pd.DataFrame]:
        """Generate all test scenarios.

        Args:
            data: Base OHLCV data.

        Returns:
            List of scenario DataFrames.
        """
        scenarios = [data]  # Original data

        # Shuffled data
        if self.config.use_shuffling:
            scenarios.extend(
                self.shuffler.shuffle_returns(data, self.config.iterations // 4)
            )
            scenarios.extend(
                self.shuffler.shuffle_blocks(data, self.config.iterations // 4)
            )

        # Noisy data
        if self.config.use_noise:
            scenarios.extend(
                self.noise_injector.add_noise(data, self.config.iterations // 4)
            )

        # Walk-forward scenarios
        if self.config.use_walk_forward:
            wf_scenarios = self.walk_forward.generate_scenarios(
                data,
                n_splits=self.config.walk_forward_splits,
            )
            scenarios.extend(wf_scenarios)

        # Block Bootstrap scenarios
        if self.config.use_block_bootstrap:
            # Distribute iterations among enabled methods
            n_methods = sum(
                [
                    self.config.use_shuffling,
                    self.config.use_noise,
                    self.config.use_sensitivity,
                    self.config.use_block_bootstrap,
                ]
            )
            n_per_method = self.config.iterations // max(1, n_methods)

            bb_samples = self.sampler.block_bootstrap(data, n_samples=n_per_method)
            scenarios.extend(bb_samples)

        # Limit total scenarios
        if len(scenarios) > self.config.iterations:
            scenarios = scenarios[: self.config.iterations]

        return scenarios
