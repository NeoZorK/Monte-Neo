"""Cache utility for Monte-Neo.

Handles caching of compiled Metal libraries, calibration results, and other expensive operations.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)

CACHE_DIR = os.path.expanduser("~/.cache/monte_neo")
_NO_PICKLE = "pickle caches are not supported: a pickle file can run code when it is loaded; use JSON"

def get_cache_path(filename: str) -> str:
    """Get absolute path for a cache file."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)  # private to the user
    return os.path.join(CACHE_DIR, filename)

def save_cache(name: str, data: Any, use_pickle: bool = False) -> bool:
    """Save data to cache."""
    if use_pickle:
        raise ValueError(_NO_PICKLE)
    try:
        path = get_cache_path(name)
        with open(path, "w") as f:
            json.dump(data, f)
        return True
    except Exception as e:
        logger.warning(f"Failed to save cache {name}: {e}")
        return False

def load_cache(name: str, use_pickle: bool = False) -> Any | None:
    """Load data from cache."""
    if use_pickle:
        raise ValueError(_NO_PICKLE)
    path = get_cache_path(name)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load cache {name}: {e}")
        return None


def get_data_hash(data: Any) -> str:
    """Generate a hash for data to use as cache key."""
    if hasattr(data, "values"):
        # For pandas objects, hash the values
        return hashlib.md5(data.values.tobytes(), usedforsecurity=False).hexdigest()  # a cache key, not a secret
    return hashlib.md5(str(data).encode(), usedforsecurity=False).hexdigest()

def save_calibration(indicator_name: str, data: Any, params: dict[str, Any]) -> bool:
    """Save optimized parameters to cache."""
    data_hash = get_data_hash(data)
    cache_name = f"calibration_{indicator_name}_{data_hash}.json"
    return save_cache(cache_name, params)

def load_calibration(indicator_name: str, data: Any) -> dict[str, Any] | None:
    """Load optimized parameters from cache."""
    data_hash = get_data_hash(data)
    cache_name = f"calibration_{indicator_name}_{data_hash}.json"
    return load_cache(cache_name)

def clear_cache(name: str | None = None) -> None:
    """Clear cache files."""
    if name:
        path = get_cache_path(name)
        if os.path.exists(path):
            os.remove(path)
    else:
        if os.path.exists(CACHE_DIR):
            for f in os.listdir(CACHE_DIR):
                os.remove(os.path.join(CACHE_DIR, f))
