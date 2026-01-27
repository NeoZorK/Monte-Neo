"""Utility configuration module."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration."""

    # Data settings
    data_dir: Path = field(default_factory=lambda: Path("./data"))
    binance_api_key: str = ""
    binance_api_secret: str = ""

    # Generation settings
    default_symbol: str = "BTCUSDT"
    default_timeframe: str = "1h"
    max_iterations: int = 1000000000
    mc_iterations: int = 1000

    # Default target metrics
    target_profit_factor: float = 2.0
    target_sharpe_ratio: float = 1.0
    target_max_drawdown: float = 0.20
    target_winrate: float = 0.45

    # Performance settings
    n_workers: int | None = None
    log_level: str = "INFO"
    use_gpu: bool = True
    gpu_precision: str = "float32"
    metal_driver: str = "cpp"


def load_config(config_path: str | Path | None = None) -> Config:
    """Load configuration from file and environment.

    Args:
        config_path: Optional path to YAML config file.

    Returns:
        Config object.
    """
    # Load environment variables
    load_dotenv()

    config = Config()

    # Override from environment
    config.data_dir = Path(os.getenv("MONTE_NEO_DATA_DIR", config.data_dir))
    config.binance_api_key = os.getenv("BINANCE_API_KEY", "")
    config.binance_api_secret = os.getenv("BINANCE_API_SECRET", "")
    config.log_level = os.getenv("MONTE_NEO_LOG_LEVEL", "INFO")

    workers = os.getenv("MONTE_NEO_WORKERS", "auto")
    config.n_workers = None if workers == "auto" else int(workers)

    # Override from YAML file
    if config_path:
        config = _merge_yaml_config(config, Path(config_path))

    return config


def _merge_yaml_config(config: Config, path: Path) -> Config:
    """Merge YAML config into Config object."""
    if not path.exists():
        return config

    with open(path) as f:
        yaml_config = yaml.safe_load(f) or {}

    # Data settings
    if "data" in yaml_config:
        data = yaml_config["data"]
        if "dir" in data:
            config.data_dir = Path(data["dir"])
        if "symbol" in data:
            config.default_symbol = data["symbol"]
        if "timeframe" in data:
            config.default_timeframe = data["timeframe"]

    # Metrics settings
    if "metrics" in yaml_config:
        metrics = yaml_config["metrics"]
        if "profit_factor" in metrics:
            config.target_profit_factor = metrics["profit_factor"]
        if "sharpe_ratio" in metrics:
            config.target_sharpe_ratio = metrics["sharpe_ratio"]
        if "max_drawdown" in metrics:
            config.target_max_drawdown = metrics["max_drawdown"]

    # Monte Carlo settings
    if "monte_carlo" in yaml_config:
        mc = yaml_config["monte_carlo"]
        if "iterations" in mc:
            config.mc_iterations = mc["iterations"]

    # Hardware settings
    if "hardware" in yaml_config:
        hw = yaml_config["hardware"]
        if "use_gpu" in hw:
            config.use_gpu = hw["use_gpu"]
        if "gpu_precision" in hw:
            config.gpu_precision = hw["gpu_precision"]
        if "metal_driver" in hw:
            config.metal_driver = hw["metal_driver"]

    return config


def save_config(config: Config, path: str | Path) -> None:
    """Save configuration to YAML file."""
    data = {
        "data": {
            "dir": str(config.data_dir),
            "symbol": config.default_symbol,
            "timeframe": config.default_timeframe,
        },
        "metrics": {
            "profit_factor": config.target_profit_factor,
            "sharpe_ratio": config.target_sharpe_ratio,
            "max_drawdown": config.target_max_drawdown,
            "winrate": config.target_winrate,
        },
        "monte_carlo": {
            "iterations": config.mc_iterations,
            "max_iterations": config.max_iterations,
        },
        "hardware": {
            "use_gpu": config.use_gpu,
            "gpu_precision": config.gpu_precision,
            "metal_driver": config.metal_driver,
        },
    }

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
