
import numpy as np
import pandas as pd

from monte_neo.core.mlx_engine import MLXBacktestEngine
from monte_neo.core.optimization.stress_tester import StressTester
from monte_neo.indicators.base import IndicatorConfig
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.utils.visualization import plot_sensitivity_heatmap, plot_stress_test_summary


def main():
    print("🎨 Generating Stress Test Visualizations...")
    
    # 1. Setup Data
    n = 1000
    data = pd.DataFrame({
        'open': np.random.randn(n).cumsum() + 100,
        'high': np.random.randn(n).cumsum() + 102,
        'low': np.random.randn(n).cumsum() + 98,
        'close': np.random.randn(n).cumsum() + 100,
        'volume': np.random.rand(n) * 1000
    }, index=pd.date_range("2023-01-01", periods=n, freq="h"))

    # 2. Indicator
    source = "data['close'] > data['close'].rolling(20).mean() & data['close'] > data['close'].rolling(50).mean()"
    indicator = DynamicIndicator(IndicatorConfig(name="DualSMA", parameters={"source_code": source}))
    
    # 3. Stress Tests
    engine = MLXBacktestEngine()
    tester = StressTester(engine)
    
    print("  Running Black Swan Test...")
    bs_results = tester.black_swan_test(data, indicator)
    
    print("  Running Sensitivity Analysis (Grid)...")
    sens_results = tester.parameter_sensitivity_analysis(data, indicator, perturbation=0.2, n_steps=7)
    
    print("  Running Breaking Point Analysis...")
    bp_results = tester.breaking_point_analysis(data, indicator)
    
    stress_results = {
        "black_swan": bs_results,
        "sensitivity": sens_results,
        "breaking_point": bp_results
    }
    
    # 4. Visualization
    print("  Generating Plots...")
    
    # Summary Plot
    plt_summary = plot_stress_test_summary(stress_results)
    plt_summary.savefig("stress_test_summary.png")
    print("  ✅ Saved stress_test_summary.png")
    
    # Heatmap Plot
    plt_heatmap = plot_sensitivity_heatmap(sens_results)
    if plt_heatmap:
        plt_heatmap.savefig("sensitivity_heatmap.png")
        print("  ✅ Saved sensitivity_heatmap.png")
    
    print("\n🚀 Visualization complete!")

if __name__ == "__main__":
    main()
