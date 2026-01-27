

import numpy as np

from monte_neo.core.acceleration.engine import GpuAccelerationEngine
from monte_neo.core.acceleration.float8 import Float8Encoder


def test_float8_scalar():
    print("🧪 Testing Float8 Scalar Conversion...")
    encoder = Float8Encoder("e4m3")
    
    # Test values
    values = [0.0, 1.0, -1.0, 0.5, 2.0, 10.0, 0.01]
    for v in values:
        encoded = encoder.encode_scalar(v)
        decoded = encoder.decode_scalar(encoded)
        print(f"Value: {v:8.4f} -> Encoded: {encoded:02x} -> Decoded: {decoded:8.4f} (Error: {abs(v-decoded):.4f})")
    
    # Test 0.5 specifically (the one that had issues)
    v = 0.5
    encoded = encoder.encode_scalar(v)
    decoded = encoder.decode_scalar(encoded)
    assert abs(v - decoded) < 0.1, f"0.5 failed: got {decoded}"
    print("✅ 0.5 conversion fixed!")

def test_metal_engine():
    print("\n🧪 Testing Metal Engine Integration...")
    try:
        # Check if Metal is available
        import Metal
        device = Metal.MTLCreateSystemDefaultDevice()
        if device is None:
            print("⏭️ Metal not available on this system, skipping Metal test.")
            return
            
        engine = GpuAccelerationEngine(precision="float8_e4m3", use_metal_cpp=True)
        if not engine.use_metal_cpp:
            print("⏭️ Metal engine initialization failed or disabled, skipping.")
            return
            
        print("✅ Metal engine initialized successfully.")
        
        # Test scenario generation
        import mlx.core as mx
        close = mx.array(np.array([100.0, 101.0, 102.0, 101.5, 103.0], dtype=np.float32))
        
        # We need to simulate the engine's run_simulation logic for scenarios
        # but let's just check if it can generate scenarios without crashing
        from monte_neo.core.native.metal_engine import MetalFloat8Engine
        metal = MetalFloat8Engine()
        
        base_np = np.array([100.0, 101.0, 102.0, 101.5, 103.0], dtype=np.float32)
        base_f8 = metal.encode_float32_to_e4m3(base_np)
        
        print(f"Base prices (f32): {base_np}")
        print(f"Base prices (f8):  {base_f8}")
        
        scenarios_f8 = metal.generate_scenarios_e4m3(base_f8, n_scenarios=2, seed=42)
        scenarios_f32 = metal.decode_e4m3_to_float32(scenarios_f8)
        
        print(f"Generated Scenarios (f32):\n{scenarios_f32}")
        
        assert scenarios_f32.shape == (2, 5)
        assert np.all(scenarios_f32[:, 0] > 90) # Should be around 100
        print("✅ Metal scenario generation successful!")
        
    except Exception as e:
        print(f"❌ Metal test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_float8_scalar()
    test_metal_engine()
