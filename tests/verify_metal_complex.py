
import pandas as pd
import numpy as np
import time
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.core.gpu_engine import MLXBacktestEngine

def main():
    # 1. Create dummy data
    n = 10000
    data = pd.DataFrame({
        'open': np.random.randn(n).astype(np.float32) + 100,
        'high': np.random.randn(n).astype(np.float32) + 101,
        'low': np.random.randn(n).astype(np.float32) + 99,
        'close': np.random.randn(n).astype(np.float32) + 100,
        'volume': np.random.randint(100, 1000, n).astype(np.float32)
    })

    # 2. Complex formula: Price > SMA(20) OR Price > High.rolling(10).max()
    # Note: Using | for OR
    from monte_neo.indicators.base import IndicatorConfig
    formula = "data['close']>data['close'].rolling(20).mean()|data['close']>data['high'].rolling(10).max()"
    indicator = DynamicIndicator(IndicatorConfig(name="test", parameters={"source_code": formula}))
    
    print(f"Testing formula: {formula}")
    metal_params = indicator.get_metal_params()
    print(f"Metal params: {metal_params}")
    
    if metal_params and metal_params[0] == 4.0 and metal_params[1] == 1.0:
        print("SUCCESS: Formula parsed correctly as strategy_type 4 with OR logic (op_type=1.0)")
    else:
        print("FAILURE: Formula NOT parsed as strategy_type 4 OR logic")
        return

    # 3. Try running with MLXBacktestEngine if available
    try:
        engine = MLXBacktestEngine()
        if engine.native_bridge is None:
            print("Native bridge not available, skipping GPU execution test")
            return
            
        # Create scenarios
        # Layout for type 4: [4, op_type, sub1, p2_1, sub2, p2_2, tp_m, ts_m]
        scenarios_params = []
        for tp in [0.1, 1.0, 10.0]:
            p = metal_params.copy()
            p[6] = tp # tp_mult
            scenarios_params.extend(p)
        
        # Convert data to Candle objects
        from monte_neo.core.acceleration.cpp_metal.metal_engine import Candle
        candles = [
            Candle(float(o), float(h), float(l), float(c), float(v)) 
            for o, h, l, c, v in zip(
                data['open'], data['high'], data['low'], data['close'], data['volume']
            )
        ]

        print(f"Running 3 scenarios on GPU via Native Bridge directly...")
        start = time.time()
        results = engine.native_bridge.run_backtest(candles, scenarios_params, 3)
        end = time.time()
        
        print(f"GPU Backtest completed in {end - start:.4f}s")
        for i, res in enumerate(results):
            print(f"Scenario {i}: Total Return = {res.total_return:.4f}, Trades = {res.trade_count}, Sharpe = {res.sharpe_ratio:.4f}")
            
    except Exception as e:
        print(f"GPU Execution failed or not available: {e}")

if __name__ == "__main__":
    main()
