from __future__ import annotations
import logging
import os
import subprocess
import time
from typing import Optional, Dict
import mlx.core as mx
from monte_neo.utils.cache import load_cache, save_cache

logger = logging.getLogger(__name__)

def try_auto_compile_metal():
    """Attempt to auto-compile Metal extension if missing."""
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "acceleration/cpp_metal/compile.sh")
        if os.path.exists(script_path):
            result = subprocess.run(["bash", script_path], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("✅ Metal extension compiled successfully.")
                return True
            else:
                logger.warning(f"❌ Auto-compilation failed: {result.stderr}")
        return False
    except Exception as e:
        logger.warning(f"⚠️ Failed to auto-compile Metal extension: {e}")
        return False

def select_best_metal_driver(metal_extension_available: bool, native_bridge_class) -> str:
    """Run a micro-benchmark to select the best Metal driver."""
    if not metal_extension_available:
        return "cpp"
        
    cached_driver = load_cache("best_metal_driver.json")
    if cached_driver:
        return cached_driver
        
    logger.info("🔍 Running micro-benchmark to select best Metal driver...")
    from monte_neo.core.acceleration.cpp_metal.metal_engine import Candle, Driver
    
    candles = [Candle(100.0, 101.0, 99.0, 100.0, 1000.0) for _ in range(1000)]
    params = [14.0, 14.0, 1.5, 3.0, 2.0] * 10000
    n_scenarios = 10000
    
    best_driver = "cpp"
    min_time = float('inf')
    
    for d_name, d_enum in [("cpp", Driver.CPP), ("objc", Driver.OBJC), ("swift", Driver.SWIFT)]:
        try:
            bridge = native_bridge_class(d_enum)
            if bridge.init():
                bridge.run_backtest(candles, params, 1000)
                start = time.perf_counter()
                bridge.run_backtest(candles, params, n_scenarios)
                duration = time.perf_counter() - start
                if duration < min_time:
                    min_time = duration
                    best_driver = d_name
        except Exception:
            pass
            
    save_cache("best_metal_driver.json", best_driver)
    return best_driver
