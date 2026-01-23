"""Data sampling module.

Generate samples for Monte Carlo simulations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class DataSampler:
    """Generate samples for Monte Carlo simulations."""

    def __init__(self, random_seed: int | None = None) -> None:
        """Initialize sampler.

        Args:
            random_seed: Random seed for reproducibility.
        """
        self.rng = np.random.default_rng(random_seed)

    def bootstrap(
        self,
        data: pd.DataFrame,
        n_samples: int = 1000,
        sample_size: int | None = None,
    ) -> list[pd.DataFrame]:
        """Generate bootstrap samples.

        Args:
            data: Source DataFrame.
            n_samples: Number of samples to generate.
            sample_size: Size of each sample (default: same as data).

        Returns:
            List of sampled DataFrames.
        """
        if sample_size is None:
            sample_size = len(data)

        samples = []
        indices = np.arange(len(data))

        for _ in range(n_samples):
            sampled_idx = self.rng.choice(indices, size=sample_size, replace=True)
            sampled_idx.sort()  # Keep time order
            samples.append(data.iloc[sampled_idx].copy())

        logger.info(f"Generated {n_samples} bootstrap samples")
        return samples

    def block_bootstrap(
        self,
        data: pd.DataFrame,
        n_samples: int = 1000,
        block_size: int | None = None,
    ) -> list[pd.DataFrame]:
        """Generate block bootstrap samples (preserves time structure).

        Args:
            data: Source DataFrame.
            n_samples: Number of samples to generate.
            block_size: Size of each block (default: sqrt(len(data))).

        Returns:
            List of sampled DataFrames.
        """
        n = len(data)
        if block_size is None:
            block_size = max(1, int(np.sqrt(n)))

        n_blocks = n // block_size
        samples = []

        for _ in range(n_samples):
            # Randomly select block start positions
            block_starts = self.rng.choice(
                n - block_size + 1,
                size=n_blocks,
                replace=True,
            )
            
            # Collect blocks
            blocks = []
            for start in block_starts:
                blocks.append(data.iloc[start : start + block_size])
            
            sample = pd.concat(blocks, ignore_index=True)
            samples.append(sample)

        logger.info(f"Generated {n_samples} block bootstrap samples (block_size={block_size})")
        return samples

    def circular_block_bootstrap(
        self,
        data: pd.DataFrame,
        n_samples: int = 1000,
        block_size: int | None = None,
    ) -> list[pd.DataFrame]:
        """Generate circular block bootstrap samples.

        Treats data as circular to avoid edge effects.

        Args:
            data: Source DataFrame.
            n_samples: Number of samples to generate.
            block_size: Size of each block.

        Returns:
            List of sampled DataFrames.
        """
        n = len(data)
        if block_size is None:
            block_size = max(1, int(np.sqrt(n)))

        n_blocks = n // block_size
        samples = []

        # Create circular data
        circular_data = pd.concat([data, data], ignore_index=True)

        for _ in range(n_samples):
            block_starts = self.rng.choice(n, size=n_blocks, replace=True)
            
            blocks = []
            for start in block_starts:
                blocks.append(circular_data.iloc[start : start + block_size])
            
            sample = pd.concat(blocks, ignore_index=True)
            samples.append(sample)

        logger.info(f"Generated {n_samples} circular block bootstrap samples")
        return samples

    def stratified_sample(
        self,
        data: pd.DataFrame,
        n_samples: int = 1000,
        strata_column: str = "returns",
        n_strata: int = 10,
    ) -> list[pd.DataFrame]:
        """Generate stratified samples based on return distribution.

        Args:
            data: Source DataFrame.
            n_samples: Number of samples to generate.
            strata_column: Column to stratify by.
            n_strata: Number of strata.

        Returns:
            List of sampled DataFrames.
        """
        # Calculate returns if not present
        df = data.copy()
        if strata_column not in df.columns:
            df["returns"] = df["close"].pct_change()
            strata_column = "returns"

        # Create strata labels
        df["strata"] = pd.qcut(
            df[strata_column].fillna(0),
            q=n_strata,
            labels=False,
            duplicates="drop",
        )

        samples = []
        strata_groups = df.groupby("strata")

        for _ in range(n_samples):
            sampled_parts = []
            for _, group in strata_groups:
                n_from_strata = max(1, len(group) // n_strata)
                sampled = group.sample(n=min(n_from_strata, len(group)), replace=True)
                sampled_parts.append(sampled)
            
            sample = pd.concat(sampled_parts, ignore_index=True).sort_index()
            sample = sample.drop(columns=["strata"])
            samples.append(sample)

        logger.info(f"Generated {n_samples} stratified samples")
        return samples

    def synthetic_data(
        self,
        data: pd.DataFrame,
        n_samples: int = 1000,
        method: str = "returns",
    ) -> list[pd.DataFrame]:
        """Generate synthetic data based on statistical properties.

        Args:
            data: Source DataFrame.
            n_samples: Number of samples to generate.
            method: Generation method ('returns', 'garch').

        Returns:
            List of synthetic DataFrames.
        """
        samples = []
        returns = data["close"].pct_change().dropna()
        
        mean_return = returns.mean()
        std_return = returns.std()

        for _ in range(n_samples):
            # Generate synthetic returns
            synthetic_returns = self.rng.normal(mean_return, std_return, len(data))
            
            # Convert to prices
            initial_price = data["close"].iloc[0]
            synthetic_prices = initial_price * np.cumprod(1 + synthetic_returns)
            
            # Create synthetic OHLCV
            sample = pd.DataFrame({
                "open": synthetic_prices * (1 + self.rng.uniform(-0.002, 0.002, len(data))),
                "high": synthetic_prices * (1 + self.rng.uniform(0, 0.01, len(data))),
                "low": synthetic_prices * (1 - self.rng.uniform(0, 0.01, len(data))),
                "close": synthetic_prices,
                "volume": data["volume"].values * self.rng.uniform(0.5, 1.5, len(data)),
            })
            samples.append(sample)

        logger.info(f"Generated {n_samples} synthetic samples")
        return samples
