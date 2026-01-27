import pandas as pd
import numpy as np
import time
from src.monte_neo.core.optimization.gpu_optimizer import GPUOptimizer

def generate_test_data(n_bars=10000):
    """Generate synthetic price data with a slight upward trend."""
    np.random.seed(42)
    close = 100 * (1 + np.cumsum(np.random.normal(0.0001, 0.01, n_bars)))
    high = close * (1 + np.random.uniform(0, 0.01, n_bars))
    low = close * (1 - np.random.uniform(0, 0.01, n_bars))
    open_p = (high + low) / 2
    volume = np.random.uniform(100, 1000, n_bars)
    
    return pd.DataFrame({
        'open': open_p, 'high': high, 'low': low, 'close': close, 'volume': volume
    })

def main():
    print("🧪 Verifying GPU Optimizer (v0.0.5)...")
    
    df = generate_test_data(50000) # 50k bars
    print(f"Data size: {len(df)} bars")
    
    optimizer = GPUOptimizer()
    
    # Define parameter grid
    param_grid = {
        'rsi_p': [10.0, 14.0, 20.0],
        'atr_p': [10.0, 14.0, 20.0],
        'sl_mult': [1.0, 2.0, 3.0],
        'tp_mult': [1.0, 2.0, 3.0],
        'ts_mult': [0.0, 1.0, 2.0] # 0 = no trailing stop
    }
    
    # Total combinations: 3 * 3 * 3 * 3 * 3 = 243
    
    start_time = time.time()
    results = optimizer.run_grid_search(df, param_grid)
    duration = time.time() - start_time
    
    print(f"✅ Grid search completed in {duration:.4f} seconds")
    print(f"Scenarios: {len(results)}")
    print(f"Speed: {len(results) / duration:.2f} scenarios/sec")
    
    # Show top results
    print("\nTop 5 Scenarios by Return:")
    print(results.sort_values('total_return', ascending=False).head())
    
    # Verify we have trades
    total_trades = results['trade_count'].sum()
    print(f"\nTotal trades across all scenarios: {total_trades}")
    
    if total_trades > 0:
        print("✅ Success: GPU backtest generated trades.")
    else:
        print("❌ Warning: No trades generated. Check strategy logic or data.")

    print("\n🚀 Verifying Walk-Forward Optimization (WFO)...")
    wfo_results = optimizer.run_walk_forward(df, param_grid, n_folds=3)
    
    print(f"Walk-Forward Efficiency (WFE): {wfo_results['wfe']:.2f}%")
    for fold in wfo_results['folds']:
        print(f"Fold {fold['fold']}: IS={fold['is_return']:.4f}, OOS={fold['oos_return']:.4f}, Params={fold['best_params']}")
    
    if wfo_results['wfe'] > 0:
        print("✅ Success: WFO calculated efficiency.")
    else:
        print("❌ Warning: WFE is 0 or negative. Possible overfitting or bad data.")

if __name__ == "__main__":
    main()
