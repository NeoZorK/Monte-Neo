
import time

import mlx.core as mx
import torch


def test_dlpack():
    print("Creating 500M elements array...")
    a = mx.zeros((50000, 10000), dtype=mx.float32)
    mx.eval(a)
    
    print("Testing torch.from_dlpack...")
    start = time.perf_counter()
    t = torch.from_dlpack(a)
    print(f"torch.from_dlpack time: {time.perf_counter() - start:.6f}s")
    print(f"Pointer: {t.data_ptr()}")
    
    # Verify it's zero-copy
    a[0, 0] = 1.23
    mx.eval(a)
    print(f"Torch value after MLX update: {t[0, 0].item()}")

if __name__ == "__main__":
    test_dlpack()
