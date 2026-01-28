import os
import yaml
from pathlib import Path
from monte_neo.utils.config import load_config, Config

def test_default_config():
    config = load_config()
    assert config.default_symbol == "BTCUSDT"
    assert config.use_gpu is True

def test_config_env_override(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "test_key")
    monkeypatch.setenv("MONTE_NEO_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("MONTE_NEO_WORKERS", "4")
    
    config = load_config()
    assert config.binance_api_key == "test_key"
    assert config.log_level == "DEBUG"
    assert config.n_workers == 4

def test_config_yaml_merge(tmp_path):
    yaml_content = {
        "data": {
            "symbol": "ETHUSDT",
            "timeframe": "15m"
        },
        "metrics": {
            "profit_factor": 3.0,
            "sharpe_ratio": 2.0
        }
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(yaml_content, f)
        
    config = load_config(config_file)
    assert config.default_symbol == "ETHUSDT"
    assert config.default_timeframe == "15m"
    assert config.target_profit_factor == 3.0
    assert config.target_sharpe_ratio == 2.0

def test_config_yaml_missing(tmp_path):
    config = load_config(tmp_path / "non_existent.yaml")
    assert config.default_symbol == "BTCUSDT" # Should remain default
