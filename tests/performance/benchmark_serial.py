import time

import numpy as np
import pandas as pd

from monte_neo.indicators.technical import SMAIndicator


def benchmark_serial():
    data_len = 5000
    n_indicators = 2000

    print(f"Generating data ({data_len} bars)...")
    df = pd.DataFrame(
        {"close": np.random.rand(data_len) * 100},
        index=pd.date_range("2020-01-01", periods=data_len, freq="min"),
    )

    indicators = []
    for i in range(n_indicators):
        ind = SMAIndicator()
        ind.set_parameter("fast_period", 5 + (i % 50))
        ind.set_parameter("slow_period", 20 + (i % 50))
        indicators.append(ind)

    print("Running serial execution...")
    start = time.time()
    for ind in indicators:
        ind.generate_signals(df)
    elapsed = time.time() - start

    ops_sec = n_indicators / elapsed
    print(f"Serial Ops/sec: {ops_sec:.2f}")

if __name__ == "__main__":
    benchmark_serial()
