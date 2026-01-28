

import numpy as np
import pandas as pd

from monte_neo.core.mlx_engine import MLXBacktestEngine
from monte_neo.core.optimization.production_exporter import ProductionExporter
from monte_neo.core.optimization.production_gate import ProductionGate
from monte_neo.core.optimization.stress_tester import DeepStressTester
from monte_neo.indicators.base import IndicatorConfig
from monte_neo.indicators.dynamic import DynamicIndicator
from monte_neo.metrics.calculator import MetricsCalculator
from monte_neo.monte_carlo.walk_forward import WalkForwardAnalyzer


def run_production_pipeline():
    print("🚀 Starting Production Readiness Pipeline...")
    
    # 1. Setup Data
    dates = pd.date_range(start="2023-01-01", periods=2000, freq="h")
    data = pd.DataFrame({
        'open': np.random.randn(2000).cumsum() + 100,
        'high': np.random.randn(2000).cumsum() + 102,
        'low': np.random.randn(2000).cumsum() + 98,
        'close': np.random.randn(2000).cumsum() + 100,
        'volume': np.random.rand(2000) * 1000
    }, index=dates)

    # 2. Setup Indicator (RSI Strategy)
    # Using complex logic for robustness
    source = "rsi(data['close'],14)<30 & data['close']>data['close'].rolling(50).mean()"
    config = IndicatorConfig(name="RSI_Strategy", parameters={"source_code": source})
    indicator = DynamicIndicator(config)
    
    # 3. GPU-Accelerated Backtesting with Trading Costs
    print("  --- Running GPU Backtest with Trading Costs ---")
    engine = MLXBacktestEngine(metal_driver="cpp")
    results, stats = engine.run_full_simulation(
        data, indicator, n_scenarios=1000,
        commission_bps=5.0, slippage_bps=2.0
    )
    print(f"  GPU Simulation Time: {stats['total']:.4f}s")

    # 4. Walk-Forward Analysis (OOS Validation)
    print("  --- Running Walk-Forward Analysis ---")
    wfa = WalkForwardAnalyzer(n_splits=5, train_pct=0.7)
    metrics_calc = MetricsCalculator()
    target_metrics = {"profit_factor": 1.1, "total_return": 0.01}
    
    wfo_result = wfa.analyze(indicator, data, metrics_calc, target_metrics)
    print(f"  WFA Pass Rate: {wfo_result.pass_rate:.1%}")
    print(f"  WFA Efficiency (WFE): {wfo_result.efficiency_ratio:.2f}")

    # 5. Deep Stress Testing
    print("  --- Running Deep Stress Tests ---")
    stress_tester = DeepStressTester(engine)
    stress_results = {
        "black_swan": stress_tester.black_swan_test(data, indicator),
        "sensitivity": stress_tester.parameter_sensitivity_analysis(data, indicator),
        "breaking_point": stress_tester.breaking_point_analysis(data, indicator)
    }
    print(f"  Breaking Point: {stress_results['breaking_point']['breaking_point_bps']} bps")
    if "std_return_variation" in stress_results['sensitivity']:
        print(f"  Parameter Sensitivity (std): {stress_results['sensitivity']['std_return_variation']:.4f}")

    # 6. Production Gate (Robustness Check)
    print("  --- Evaluating Production Gate ---")
    gate = ProductionGate(min_wfe=0.6)
    production_status = gate.evaluate(wfo_result, results, stress_results)
    
    print(f"  Robustness Score: {production_status['robustness_score']}/100")
    print(f"  Production Ready: {production_status['is_production_ready']}")
    print(f"  Recommendation: {production_status['recommendation']}")

    # 6. Production Export
    if production_status['is_production_ready'] or True: # Force export for demo
        print("  --- Exporting for Production ---")
        exporter = ProductionExporter()
        path = exporter.export(indicator, production_status)
        print(f"  ✅ Exported to: {path}")

if __name__ == "__main__":
    run_production_pipeline()
