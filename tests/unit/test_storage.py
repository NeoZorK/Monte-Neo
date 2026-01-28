import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from monte_neo.data.storage import ParquetStorage

@pytest.fixture
def temp_storage(tmp_path):
    return ParquetStorage(base_dir=tmp_path)

@pytest.fixture
def sample_df():
    df = pd.DataFrame({
        "open": [100.0, 101.0],
        "high": [102.0, 103.0],
        "low": [98.0, 99.0],
        "close": [101.0, 102.0],
        "volume": [1000, 1100]
    })
    df.index = pd.to_datetime(["2023-01-01", "2023-01-02"])
    return df

def test_parquet_storage_save_load(temp_storage, sample_df):
    symbol = "BTCUSDT"
    timeframe = "1h"
    
    # Save
    path = temp_storage.save(sample_df, symbol, timeframe)
    assert path.exists()
    assert symbol in path.name
    
    # Exists
    assert temp_storage.exists(symbol, timeframe)
    
    # Load
    loaded_df = temp_storage.load(symbol, timeframe)
    assert len(loaded_df) == 2
    assert "close" in loaded_df.columns
    assert loaded_df.iloc[0]["close"] == 101.0

def test_parquet_storage_list_delete(temp_storage, sample_df):
    temp_storage.save(sample_df, "BTCUSDT", "1h")
    temp_storage.save(sample_df, "ETHUSDT", "1h")
    
    files = temp_storage.list_files()
    assert len(files) == 2
    symbols = [f["symbol"] for f in files]
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols
    
    # Delete
    assert temp_storage.delete("BTCUSDT", "1h")
    assert not temp_storage.exists("BTCUSDT", "1h")
    assert len(temp_storage.list_files()) == 1

def test_parquet_storage_get_info(temp_storage, sample_df):
    temp_storage.save(sample_df, "BTCUSDT", "1h")
    info = temp_storage.get_info("BTCUSDT", "1h")
    
    assert info is not None
    assert info["rows"] == 2
    assert len(info["columns"]) >= 5
