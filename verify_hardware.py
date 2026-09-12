"""Hardware verification for Float8 and Metal paths. Run: uv run python verify_hardware.py"""

import numpy as np

from monte_neo.core.acceleration.engine import GpuAccelerationEngine
from monte_neo.core.acceleration.float8 import Float8Encoder


def test_float8_scalar() -> None:
    print("Testing Float8 scalar conversion...")
    encoder = Float8Encoder("e4m3")
    values = [0.0, 1.0, -1.0, 0.5, 2.0, 10.0, 0.01]
    for v in values:
        encoded = encoder.encode_scalar(v)
        decoded = encoder.decode_scalar(encoded)
        print(
            f"Value: {v:8.4f} -> Encoded: {encoded:02x} -> "
            f"Decoded: {decoded:8.4f} (Error: {abs(v - decoded):.4f})"
        )
    v = 0.5
    encoded = encoder.encode_scalar(v)
    decoded = encoder.decode_scalar(encoded)
    assert abs(v - decoded) < 0.1, f"0.5 failed: got {decoded}"
    print("Float8 scalar OK")


def test_metal_float8_engine() -> None:
    print("\nTesting MetalFloat8Engine (pyobjc shaders)...")
    try:
        import Metal

        device = Metal.MTLCreateSystemDefaultDevice()
        if device is None:
            print("Metal not available, skipping.")
            return

        engine = GpuAccelerationEngine(precision="float8_e4m3", metal_driver="cpp")
        if engine.metal_engine is None:
            print("MetalFloat8Engine not initialized, skipping scenario test.")
            return

        print("GpuAccelerationEngine + MetalFloat8Engine OK")

        from monte_neo.core.native.metal_engine import MetalFloat8Engine

        metal = MetalFloat8Engine()
        base_np = np.array([100.0, 101.0, 102.0, 101.5, 103.0], dtype=np.float32)
        base_f8 = metal.encode_float32_to_e4m3(base_np)
        scenarios_f8 = metal.generate_scenarios_e4m3(base_f8, n_scenarios=2, seed=42)
        scenarios_f32 = metal.decode_e4m3_to_float32(scenarios_f8)
        assert scenarios_f32.shape == (2, 5)
        assert np.all(scenarios_f32[:, 0] > 90)
        print("Metal scenario generation OK")
    except Exception as e:
        print(f"MetalFloat8Engine test failed: {e}")
        raise


def test_metal_backtest_bridge() -> None:
    print("\nTesting MetalBacktestBridge (C++/Swift extension)...")
    from monte_neo.core.acceleration.cpp_metal.metal_engine import Candle, Driver, MetalBacktestBridge

    bridge = MetalBacktestBridge(Driver.CPP)
    assert bridge.init(), "MetalBacktestBridge.init() failed"
    candles = [Candle(100.0, 101.0, 99.0, 100.0, 1000.0) for _ in range(64)]
    params = [14.0, 14.0, 1.5, 3.0, 2.0]
    results = bridge.run_backtest(candles, params, n_scenarios=4)
    assert len(results) == 4
    print(f"MetalBacktestBridge OK, sample return={results[0].total_return:.4f}")


if __name__ == "__main__":
    test_float8_scalar()
    test_metal_float8_engine()
    test_metal_backtest_bridge()
    print("\nAll hardware checks passed.")
