
import mlx.core as mx
import numpy as np
import time

def test_ptr():
    # 500M elements = 2GB for float32
    print("Creating 500M elements array...")
    a = mx.zeros((50000, 10000), dtype=mx.float32)
    mx.eval(a)
    
    print("Testing np.array(a)...")
    start = time.perf_counter()
    b = np.array(a)
    print(f"np.array(a) time: {time.perf_counter() - start:.6f}s")
    
    print("Testing np.frombuffer(memoryview(a))...")
    try:
        start = time.perf_counter()
        m = memoryview(a)
        b = np.frombuffer(m, dtype=np.float32)
        print(f"np.frombuffer time: {time.perf_counter() - start:.6f}s")
        print(f"Shape: {b.shape}")
        
        # Verify zero-copy
        a.view(-1)[0] = 9.99
        mx.eval(a)
        print(f"NumPy value after MLX update: {b[0]}")
    except Exception as e:
        print(f"np.frombuffer failed: {e}")

if __name__ == "__main__":
    test_ptr()
