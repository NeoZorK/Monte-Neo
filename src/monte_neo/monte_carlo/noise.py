"""Noise injection module.

Adds various types of noise to test indicator robustness.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class NoiseInjector:
    """Noise injection for robustness testing."""

    def __init__(self, random_seed: int | None = None) -> None:
        """Initialize noise injector.

        Args:
            random_seed: Random seed for reproducibility.
        """
        self.rng = np.random.default_rng(random_seed)

    def add_noise(
        self,
        data: pd.DataFrame,
        n_samples: int = 100,
        noise_level: float = 0.001,
    ) -> list[pd.DataFrame]:
        """Add Gaussian noise to price data.

        Args:
            data: OHLCV DataFrame.
            n_samples: Number of noisy samples.
            noise_level: Standard deviation as fraction of price.

        Returns:
            List of noisy DataFrames.
        """
        samples = []

        for _ in range(n_samples):
            sample = data.copy()

            for col in ["open", "high", "low", "close"]:
                noise = self.rng.normal(0, noise_level, len(data))
                sample[col] = sample[col] * (1 + noise)

            # Ensure OHLC consistency
            sample = self._fix_ohlc(sample)
            samples.append(sample)

        logger.debug(f"Generated {n_samples} Gaussian noise samples")
        return samples

    def add_slippage(
        self,
        data: pd.DataFrame,
        n_samples: int = 100,
        slippage_bps: float = 5.0,
    ) -> list[pd.DataFrame]:
        """Simulate price slippage.

        Args:
            data: OHLCV DataFrame.
            n_samples: Number of samples.
            slippage_bps: Slippage in basis points.

        Returns:
            List of DataFrames with slippage.
        """
        samples = []
        slippage_pct = slippage_bps / 10000

        for _ in range(n_samples):
            sample = data.copy()

            # Random slippage direction and magnitude
            slippage = self.rng.uniform(-slippage_pct, slippage_pct, len(data))

            # Apply to all prices
            for col in ["open", "high", "low", "close"]:
                sample[col] = sample[col] * (1 + slippage)

            sample = self._fix_ohlc(sample)
            samples.append(sample)

        logger.debug(f"Generated {n_samples} slippage samples ({slippage_bps} bps)")
        return samples

    def add_spread_variation(
        self,
        data: pd.DataFrame,
        n_samples: int = 100,
        base_spread_bps: float = 2.0,
        volatility_multiplier: float = 2.0,
    ) -> list[pd.DataFrame]:
        """Add variable spread simulation.

        Args:
            data: OHLCV DataFrame.
            n_samples: Number of samples.
            base_spread_bps: Base spread in basis points.
            volatility_multiplier: Spread increase during high volatility.

        Returns:
            List of DataFrames with spread effects.
        """
        samples = []
        base_spread = base_spread_bps / 10000

        # Estimate volatility
        returns = data["close"].pct_change().fillna(0)
        rolling_vol = returns.rolling(20, min_periods=1).std()
        normalized_vol = rolling_vol / rolling_vol.mean()

        for _ in range(n_samples):
            sample = data.copy()

            # Variable spread based on volatility
            spread = base_spread * (1 + (normalized_vol - 1) * volatility_multiplier)
            spread = spread.clip(base_spread, base_spread * 10)  # Cap at 10x

            # Apply to open/close (entry/exit simulation)
            direction = self.rng.choice([-1, 1], len(data))
            sample["close"] = sample["close"] * (1 + spread.values * direction * 0.5)

            sample = self._fix_ohlc(sample)
            samples.append(sample)

        logger.debug(f"Generated {n_samples} spread variation samples")
        return samples

    def add_gap_noise(
        self,
        data: pd.DataFrame,
        n_samples: int = 100,
        gap_probability: float = 0.05,
        max_gap_pct: float = 0.02,
    ) -> list[pd.DataFrame]:
        """Add random gaps between candles.

        Args:
            data: OHLCV DataFrame.
            n_samples: Number of samples.
            gap_probability: Probability of gap per candle.
            max_gap_pct: Maximum gap as fraction of price.

        Returns:
            List of DataFrames with gaps.
        """
        samples = []

        for _ in range(n_samples):
            sample = data.copy()

            # Generate random gaps
            has_gap = self.rng.random(len(data)) < gap_probability
            gap_size = self.rng.uniform(-max_gap_pct, max_gap_pct, len(data))
            gap_size = gap_size * has_gap

            # Apply cumulative gaps
            gap_factor = np.cumprod(1 + gap_size)

            for col in ["open", "high", "low", "close"]:
                sample[col] = sample[col] * gap_factor

            sample = self._fix_ohlc(sample)
            samples.append(sample)

        logger.debug(f"Generated {n_samples} gap noise samples")
        return samples

    def add_volume_noise(
        self,
        data: pd.DataFrame,
        n_samples: int = 100,
        noise_level: float = 0.3,
    ) -> list[pd.DataFrame]:
        """Add noise to volume data.

        Args:
            data: OHLCV DataFrame.
            n_samples: Number of samples.
            noise_level: Standard deviation as fraction of volume.

        Returns:
            List of DataFrames with volume noise.
        """
        samples = []

        for _ in range(n_samples):
            sample = data.copy()

            noise = self.rng.lognormal(0, noise_level, len(data))
            sample["volume"] = sample["volume"] * noise
            sample["volume"] = sample["volume"].clip(lower=0)

            samples.append(sample)

        logger.debug(f"Generated {n_samples} volume noise samples")
        return samples

    def add_latency_shift(
        self,
        data: pd.DataFrame,
        n_samples: int = 100,
        max_shift: int = 2,
    ) -> list[pd.DataFrame]:
        """Simulate execution latency by shifting data relative to itself.
        
        Args:
            data: OHLCV DataFrame.
            n_samples: Number of samples.
            max_shift: Maximum number of candles to shift.
            
        Returns:
            List of DataFrames with latency shifts.
        """
        samples = []
        
        for _ in range(n_samples):
            shift = self.rng.integers(1, max_shift + 1)
            sample = data.copy()
            
            # Shift prices forward (making signals appear late)
            # Actually, shifting prices backward has same effect as delaying signals
            sample = sample.shift(shift)
            sample = sample.bfill()
            
            samples.append(sample)
            
        logger.debug(f"Generated {n_samples} latency shift samples (max {max_shift} candles)")
        return samples

    def _fix_ohlc(self, data: pd.DataFrame) -> pd.DataFrame:
        """Ensure OHLC consistency.

        Args:
            data: OHLCV DataFrame.

        Returns:
            Fixed DataFrame.
        """
        data = data.copy()

        # High must be >= max(open, close)
        data["high"] = data[["open", "high", "close"]].max(axis=1)

        # Low must be <= min(open, close)
        data["low"] = data[["open", "low", "close"]].min(axis=1)

        return data
