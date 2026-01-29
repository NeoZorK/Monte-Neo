import numpy as np
import pandas as pd
import mlx.core as mx
from monte_neo.core.mlx_engine import MLXBacktestEngine
from monte_neo.indicators.base import BaseIndicator
from monte_neo.metrics.calculator import MetricsCalculator

class SimpleMovingAverage(BaseIndicator):
    def __init__(self, period=20):
        super().__init__()
        self.period = period
    def calculate(self, data): return pd.Series(data['close']).rolling(self.period).mean()
    def generate_signals(self, data): return self.generate_signals_fast(data)
    def generate_signals_fast(self, data):
        close = data['close'].values
        ma = pd.Series(close).rolling(self.period).mean().values
        signals = np.zeros(len(close), dtype=np.int32)
        signals[close > ma] = 1
        signals[close < ma] = -1
        return signals
    def to_mlx_representation(self):
        class MLXStrat:
            def __init__(self, period): self.period = period
            def generate_signals(self, scenarios):
                # scenarios: [Scen, Time]
                # Implement SMA using convolution in MLX
                # Pad for same length
                padded = mx.pad(scenarios, ((0,0), (self.period-1, 0)), constant_values=scenarios[:, 0:1])
                # We need to reshape for conv1d: [N, L, C]
                x = padded[:, :, None]
                weight = mx.full((1, self.period, 1), 1.0 / self.period)
                ma = mx.conv1d(x, weight)[:, :, 0]
                
                signals = mx.zeros(scenarios.shape, dtype=mx.int32)
                signals = mx.where(scenarios > ma, 1, signals)
                signals = mx.where(scenarios < ma, -1, signals)
                
                # Zero out first period-1 signals to match Numba/Pandas
                if self.period > 1:
                    mask = mx.arange(scenarios.shape[1])[None, :] >= (self.period - 1)
                    signals = mx.where(mask, signals, 0)
                
                return signals
        return MLXStrat(self.period)

def verify_accuracy():
    print("🚀 Verifying Metrics Accuracy (Metal vs Numba)...")
    
    # Generate dummy data
    np.random.seed(42)
    n_time = 1000
    data = pd.DataFrame({
        'open': np.random.randn(n_time).cumsum() + 100,
        'high': np.random.randn(n_time).cumsum() + 101,
        'low': np.random.randn(n_time).cumsum() + 99,
        'close': np.random.randn(n_time).cumsum() + 100,
        'volume': np.random.rand(n_time) * 1000
    })
    
    engine = MLXBacktestEngine()
    indicators = [SimpleMovingAverage(20), SimpleMovingAverage(50)]
    n_scenarios = 5
    
    # 1. Run with 3D Engine (Metal)
    scenarios_mx = mx.array(data['close'].values[None, :].repeat(n_scenarios, axis=0))
    results_metal = engine.backtest_3d(
        indicators=indicators,
        data=data,
        scenarios=scenarios_mx,
        use_sl_tp=True,
        sl_pct=2.0,
        tp_pct=4.0,
        commission_bps=0.0,
        slippage_bps=0.0
    )
    
    # Get signals for comparison
    mlx_strat = indicators[0].to_mlx_representation()
    signals_mlx = mlx_strat.generate_signals(scenarios_mx[0:1])
    signals_mlx_np = np.array(signals_mlx[0]).astype(np.int32)
    
    print("\n📊 Results Comparison (Ind 0, Scen 0):")
    m = results_metal[0][0]['metrics']
    print(f"Metal: Return={m['total_return']:.4f}, Trades={m['trade_count']}, PF={m['profit_factor']:.4f}, MaxDD={m['max_drawdown']:.4f}")
    
    # Calculate Numba baseline for Ind 0
    signals_numba = indicators[0].generate_signals_fast(data)
    
    # Compare signals
    diff_count = np.sum(signals_mlx_np != signals_numba)
    print(f"Signal differences: {diff_count} / {len(signals_numba)}")
    if diff_count > 0:
        first_diff = np.where(signals_mlx_np != signals_numba)[0][0]
        print(f"First diff at index {first_diff}: MLX={signals_mlx_np[first_diff]}, Numba={signals_numba[first_diff]}")
        print(f"Close price at {first_diff}: {data['close'].values[first_diff]}")
        ma_numba = pd.Series(data['close'].values).rolling(indicators[0].period).mean().values[first_diff]
        print(f"MA Numba at {first_diff}: {ma_numba}")

    signals_0 = signals_numba.reshape(1, -1)
    close_np = data['close'].values.astype(np.float64)
    numba_res = MetricsCalculator.calculate_batch_fast(
        close_np, close_np, close_np, signals_0, True, 2.0, 4.0,
        commission_pct=0.0, slippage_pct=0.0
    )
    
    # Numba results: [total_return, max_dd, pf, n_trades]
    n_ret, n_max_dd, n_pf, n_trades = numba_res[0]
    print(f"Numba: Return={n_ret:.4f}, Trades={int(n_trades)}, PF={n_pf:.4f}, MaxDD={n_max_dd:.4f}")
    
    # Check if they are close
    assert np.allclose(m['total_return'], n_ret, atol=1e-3)
    assert np.allclose(m['max_drawdown'], n_max_dd, atol=1e-3)
    assert m['trade_count'] == int(n_trades)
    assert np.allclose(m['profit_factor'], n_pf, atol=1e-2)
    
    print("\n✅ Accuracy Check Passed!")

if __name__ == "__main__":
    verify_accuracy()
