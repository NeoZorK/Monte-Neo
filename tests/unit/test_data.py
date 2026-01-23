"""Unit tests for data handling."""

import pytest
import os
import pandas as pd
import numpy as np
from pathlib import Path
from monte_neo.data.storage import ParquetStorage
from monte_neo.data.sampler import DataSampler

def test_parquet_storage(tmp_path):
    storage = ParquetStorage(tmp_path)
    data = pd.DataFrame({
        "close": [100.0, 101.0, 102.0],
        "volume": [10, 20, 30]
    }, index=pd.date_range("2024-01-01", periods=3, freq="1h"))
    
    # Save
    storage.save(data, "TEST", "1h")
    assert (tmp_path / "raw" / "TEST_1h.parquet").exists()
    
    # Load
    loaded = storage.load("TEST", "1h")
    assert len(loaded) == 3
    assert loaded["close"].iloc[0] == 100.0
    
    # List
    files = storage.list_files()
    assert len(files) == 1
    assert files[0]["symbol"] == "TEST"

def test_data_sampler(sample_ohlcv):
    sampler = DataSampler(random_seed=42)
    
    # Bootstrap
    boot = sampler.bootstrap(sample_ohlcv, n_samples=5)
    assert len(boot) == 5
    assert len(boot[0]) == len(sample_ohlcv)
    
    # Block bootstrap
    block = sampler.block_bootstrap(sample_ohlcv, n_samples=5, block_size=10)
    assert len(block) == 5
    
    # Noise injection
    noisy = sampler.inject_noise(sample_ohlcv, noise_scale=0.01)
    assert len(noisy) == len(sample_ohlcv)
    assert not noisy["close"].equals(sample_ohlcv["close"])
