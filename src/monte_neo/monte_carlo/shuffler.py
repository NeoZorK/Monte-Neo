"""Data shuffling module.

Implements various shuffling methods for Monte Carlo robustness testing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class DataShuffler:
    """Data shuffling for robustness testing."""

    def __init__(self, random_seed: int | None = None) -> None:
        """Initialize shuffler.

        Args:
            random_seed: Random seed for reproducibility.
        """
        self.rng = np.random.default_rng(random_seed)

    def shuffle_returns(
        self,
        data: pd.DataFrame,
        n_samples: int = 100,
    ) -> list[pd.DataFrame]:
        """Shuffle returns while preserving distribution.

        This shuffles the order of returns, breaking time dependency.

        Args:
            data: OHLCV DataFrame.
            n_samples: Number of shuffled samples.

        Returns:
            List of shuffled DataFrames.
        """
        samples = []
        returns = data["close"].pct_change().fillna(0).values

        for _ in range(n_samples):
            # Shuffle returns
            shuffled_returns = self.rng.permutation(returns)

            # Reconstruct prices
            initial_price = data["close"].iloc[0]
            new_prices = initial_price * np.cumprod(1 + shuffled_returns)

            # Create shuffled OHLCV
            sample = self._reconstruct_ohlcv(data, new_prices)
            samples.append(sample)

        logger.debug(f"Generated {n_samples} return-shuffled samples")
        return samples

    def shuffle_blocks(
        self,
        data: pd.DataFrame,
        n_samples: int = 100,
        block_size: int | None = None,
    ) -> list[pd.DataFrame]:
        """Shuffle blocks of data.

        Preserves short-term structure but breaks long-term patterns.

        Args:
            data: OHLCV DataFrame.
            n_samples: Number of shuffled samples.
            block_size: Size of each block.

        Returns:
            List of shuffled DataFrames.
        """
        n = len(data)
        if block_size is None:
            block_size = max(10, n // 20)  # ~5% of data per block

        n_blocks = n // block_size
        samples = []

        for _ in range(n_samples):
            # Create block indices
            block_indices = list(range(n_blocks))
            self.rng.shuffle(block_indices)

            # Collect shuffled blocks
            parts = []
            for block_idx in block_indices:
                start = block_idx * block_size
                end = start + block_size
                parts.append(data.iloc[start:end])

            # Handle remainder
            remainder_start = n_blocks * block_size
            if remainder_start < n:
                parts.append(data.iloc[remainder_start:])

            sample = pd.concat(parts, ignore_index=True)
            samples.append(sample)

        logger.debug(f"Generated {n_samples} block-shuffled samples")
        return samples

    def shuffle_within_session(
        self,
        data: pd.DataFrame,
        n_samples: int = 100,
        session_hours: int = 24,
    ) -> list[pd.DataFrame]:
        """Shuffle candles within trading sessions.

        Useful for intraday data where sessions are independent.

        Args:
            data: OHLCV DataFrame with datetime index.
            n_samples: Number of shuffled samples.
            session_hours: Hours per session.

        Returns:
            List of shuffled DataFrames.
        """
        samples = []

        # Group by session
        if hasattr(data.index, 'date'):
            data = data.copy()
            data["session"] = pd.to_datetime(data.index).date
        else:
            # Assume uniform spacing, create synthetic sessions
            session_size = session_hours
            data = data.copy()
            data["session"] = np.arange(len(data)) // session_size

        sessions = data.groupby("session")

        for _ in range(n_samples):
            shuffled_parts = []

            for _, session_data in sessions:
                # Shuffle within session
                shuffled = session_data.sample(
                    frac=1, random_state=int(self.rng.integers(1e9))
                )
                shuffled_parts.append(shuffled)

            sample = pd.concat(shuffled_parts)
            sample = sample.drop(columns=["session"])
            samples.append(sample)

        logger.debug(f"Generated {n_samples} session-shuffled samples")
        return samples

    def shuffle_columns(
        self,
        data: pd.DataFrame,
        n_samples: int = 100,
        columns: list[str] | None = None,
    ) -> list[pd.DataFrame]:
        """Shuffle specific columns independently.

        Tests sensitivity to inter-column relationships.

        Args:
            data: OHLCV DataFrame.
            n_samples: Number of shuffled samples.
            columns: Columns to shuffle (default: volume only).

        Returns:
            List of shuffled DataFrames.
        """
        if columns is None:
            columns = ["volume"]  # Safe default - don't break OHLC relationship

        samples = []

        for _ in range(n_samples):
            sample = data.copy()

            for col in columns:
                if col in sample.columns:
                    sample[col] = self.rng.permutation(sample[col].values)

            samples.append(sample)

        logger.debug(f"Generated {n_samples} column-shuffled samples")
        return samples

    def _reconstruct_ohlcv(
        self,
        original: pd.DataFrame,
        new_close: np.ndarray,
    ) -> pd.DataFrame:
        """Reconstruct OHLCV from new close prices.

        Args:
            original: Original OHLCV data.
            new_close: New close prices.

        Returns:
            Reconstructed OHLCV DataFrame.
        """
        # Calculate original ratios
        o_ratio = original["open"] / original["close"]
        h_ratio = original["high"] / original["close"]
        l_ratio = original["low"] / original["close"]

        # Apply to new close
        sample = pd.DataFrame({
            "open": new_close * o_ratio.values,
            "high": new_close * h_ratio.values,
            "low": new_close * l_ratio.values,
            "close": new_close,
            "volume": original["volume"].values,
        })

        # Ensure high >= max(open, close) and low <= min(open, close)
        sample["high"] = sample[["open", "high", "close"]].max(axis=1)
        sample["low"] = sample[["open", "low", "close"]].min(axis=1)

        return sample
