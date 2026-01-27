
import pandas as pd
import numpy as np
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.indicators.base import IndicatorConfig
from monte_neo.core.mlx_engine import MLXBacktestEngine
from monte_neo.metrics.calculator import MetricsCalculator

def test_bb_metal():
    # 1. Create data
    data = pd.DataFrame({
        "open": np.random.randn(1000).cumsum() + 100,
        "high": np.random.randn(1000).cumsum() + 102,
        "low": np.random.randn(1000).cumsum() + 98,
        "close": np.random.randn(1000).cumsum() + 100,
        "volume": np.random.rand(1000) * 1000
    })
    
    # 2. Create BB indicator
    bb_code = "data['close'] < (data['close'].rolling(20).mean() - 2.0 * data['close'].rolling(20).std())"
    config = IndicatorConfig(name="BB_Test", parameters={"source_code": bb_code})
    indicator = DynamicIndicator(config)
    
    # 3. Check metal params
    params = indicator.get_metal_params()
    print(f"Metal Params: {params}")
    
    if params and params[0] == 5.0:
        print("✅ BB pattern recognized correctly for Metal!")
    else:
        print("❌ BB pattern NOT recognized correctly.")
        return

    # 4. Run through MLX engine
    engine = MLXBacktestEngine()
    results, timing = engine.run_full_simulation(data, indicator, 100)
    print(f"Backtest Result (Total Return): {results[0]['metrics']['total_return']:.2%}")
    print(f"Timing: {timing}")

if __name__ == "__main__":
    test_bb_metal()
