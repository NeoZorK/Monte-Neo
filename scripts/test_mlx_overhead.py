
import time

import mlx.core as mx


def test_mlx_overhead():
    n_pop = 1000
    n_scen = 100
    n_time = 5000
    
    close = mx.zeros((n_scen, n_time))
    mx.eval(close)
    
    start = time.perf_counter()
    all_signals = []
    for i in range(n_pop):
        # Minimal op
        sig = close + i
        all_signals.append(sig)
    
    signal_tensor = mx.stack(all_signals)
    mx.eval(signal_tensor)
    print(f"1000 simple ops + stack + eval: {time.perf_counter() - start:.6f}s")

if __name__ == "__main__":
    test_mlx_overhead()
