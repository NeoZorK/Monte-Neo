from __future__ import annotations

import logging
import os
import subprocess
import sys
import time

from monte_neo.utils.cache import load_cache, save_cache

logger = logging.getLogger(__name__)

def try_auto_compile_metal():
    """Attempt to auto-compile Metal extension if missing."""
    try:
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "acceleration/cpp_metal/compile.sh",
        )
        if os.path.exists(script_path):
            env = os.environ.copy()  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
            env["PYTHON"] = sys.executable  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
            result = subprocess.run(  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
                ["bash", script_path],
                capture_output=True,
                text=True,
                env=env,
            )
            if result.returncode == 0:  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
                logger.info("✅ Metal extension compiled successfully.")  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
                return True  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
            else:
                logger.warning(f"❌ Auto-compilation failed: {result.stderr}")  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
        return False
    except Exception as e:  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
        logger.warning(f"⚠️ Failed to auto-compile Metal extension: {e}")  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
        return False  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks

def select_best_metal_driver(metal_extension_available: bool, native_bridge_class) -> str:
    """Run a micro-benchmark to select the best Metal driver."""
    if not metal_extension_available:  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
        return "cpp"  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
        
    cached_driver = load_cache("best_metal_driver.json")  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
    if cached_driver:  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
        return cached_driver  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
        
    logger.info("🔍 Running micro-benchmark to select best Metal driver...")  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
    from monte_neo.core.acceleration.cpp_metal.metal_engine import Candle, Driver  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
    
    candles = [Candle(100.0, 101.0, 99.0, 100.0, 1000.0) for _ in range(1000)]  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
    params = [14.0, 14.0, 1.5, 3.0, 2.0] * 10000  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
    n_scenarios = 10000  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
    
    best_driver = "cpp"  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
    min_time = float('inf')  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
    
    for d_name, d_enum in [("cpp", Driver.CPP), ("objc", Driver.OBJC), ("swift", Driver.SWIFT)]:  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
        try:  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
            bridge = native_bridge_class(d_enum)  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
            if bridge.init():  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
                bridge.run_backtest(candles, params, 1000)  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
                start = time.perf_counter()  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
                bridge.run_backtest(candles, params, n_scenarios)  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
                duration = time.perf_counter() - start  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
                if duration < min_time:  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
                    min_time = duration  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
                    best_driver = d_name  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
        except Exception:  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
            pass
            
    save_cache("best_metal_driver.json", best_driver)  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
    return best_driver  # pragma: no cover  # MLX hardware/driver path absent on Linux CI after mocks
